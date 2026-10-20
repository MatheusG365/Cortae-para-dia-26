"""Authenticated Drive writes and bounded, explicit public-media reads."""
import json
import hashlib
import re
import uuid
import threading
from collections import OrderedDict
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account

SCOPE = 'https://www.googleapis.com/auth/drive.file'
FILE_ID = re.compile(r'^[A-Za-z0-9_-]{10,200}$')
BASE = 'https://www.googleapis.com/drive/v3/files'
UPLOAD = 'https://www.googleapis.com/upload/drive/v3/files'
TOKEN_URIS = {'https://oauth2.googleapis.com/token', 'https://accounts.google.com/o/oauth2/token'}
_CREDENTIALS = OrderedDict()
_CACHE_LOCK = threading.RLock()
PUBLIC_AREAS = frozenset({'site', 'mobile', 'perfil', 'barbearia', 'marketplace', 'visagismo/cortes'})
PUBLIC_PROVIDER = 'public_google_drive'
PUBLIC_MAX_BYTES = 5 * 1024 * 1024


class DriveError(Exception):
    """Safe message suitable for a storage boundary, never provider response text."""


class _BoundedAuthRequest:
    def __init__(self, session):
        self.request = Request(session=session)

    def __call__(self, url, method='GET', body=None, headers=None, timeout=None, **kwargs):
        if url not in TOKEN_URIS:
            raise DriveError('Endpoint de autenticação do Drive inválido.')
        return self.request(url=url, method=method, body=body, headers=headers,
                            timeout=20, allow_redirects=False)


class GoogleDriveStorage:
    name = 'google_drive'

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.trust_env = False
        try:
            # Hosted deployments can keep the authorization in their secret store.
            # A supplied invalid secret must fail closed, never use an older file.
            raw = config.get('GOOGLE_DRIVE_CREDENTIALS_JSON')
            if raw:
                if not isinstance(raw, str) or len(raw.encode('utf-8')) > 65536:
                    raise ValueError('credentials')
                info = json.loads(raw)
                source_key = ('environment', hashlib.sha256(raw.encode('utf-8')).hexdigest())
            else:
                path = Path(config.get('GOOGLE_DRIVE_CREDENTIALS_FILE') or '')
                if not path.is_file() or path.is_symlink() or path.stat().st_size > 65536:
                    raise ValueError('credentials')
                info = json.loads(path.read_text(encoding='utf-8-sig'))
                file_stat = path.stat()
                source_key = ('file', str(path.resolve()), file_stat.st_mtime_ns, file_stat.st_size)
            if not isinstance(info, dict):
                raise ValueError('credentials')
            if info.get('token_uri', 'https://oauth2.googleapis.com/token') not in TOKEN_URIS:
                raise ValueError('token endpoint')
            if info.get('universe_domain', 'googleapis.com') != 'googleapis.com':
                raise ValueError('universe')
            cache_key = source_key + (bool(config.get('GOOGLE_DRIVE_SHARED_DRIVE_ID')),)
            with _CACHE_LOCK:
                cached = _CREDENTIALS.get(cache_key)
            if cached:
                self.credentials, self.credentials_lock = cached
            elif info.get('type') == 'authorized_user':
                # Discard alternate token URLs: refresh credentials never choose an external host.
                scopes = info.get('scopes') or [SCOPE]
                if isinstance(scopes, str):
                    scopes = scopes.split()
                if not ({SCOPE, 'https://www.googleapis.com/auth/drive'} & set(scopes)):
                    raise ValueError('missing Drive authorization')
                # Existing full-Drive authorization must remain explicit in the local
                # OAuth file; never silently request a broader scope here.
                self.credentials = Credentials.from_authorized_user_info(info, scopes=scopes)
            elif info.get('type') == 'service_account' and config.get('GOOGLE_DRIVE_SHARED_DRIVE_ID'):
                self.credentials = service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
            else:
                raise ValueError('credential type')
            if not cached:
                self.credentials_lock = threading.RLock()
                with _CACHE_LOCK:
                    self.credentials, self.credentials_lock = _CREDENTIALS.setdefault(
                        cache_key, (self.credentials, self.credentials_lock))
                    while len(_CREDENTIALS) > 4:
                        _CREDENTIALS.popitem(last=False)
            folders = config.get('GOOGLE_DRIVE_FOLDER_IDS') or {}
            if config.get('GOOGLE_DRIVE_FOLDER_IDS_FILE'):
                folder_path = Path(config['GOOGLE_DRIVE_FOLDER_IDS_FILE'])
                if not folder_path.is_file() or folder_path.is_symlink() or folder_path.stat().st_size > 65536:
                    raise ValueError('folders file')
                folders = json.loads(folder_path.read_text(encoding='utf-8-sig'))
            self.folders = json.loads(folders) if isinstance(folders, str) else folders
            if not isinstance(self.folders, dict):
                raise ValueError('folders')
        except Exception:
            raise DriveError('Armazenamento Google Drive não configurado. Configure a autorização e as pastas no servidor.') from None

    def _request(self, method, url, *, limit=1048576, **kwargs):
        if not (url == BASE or url == UPLOAD or url.startswith(BASE + '/')):
            raise DriveError('Endpoint de armazenamento inválido.')
        headers = dict(kwargs.pop('headers', {}))
        try:
            with self.credentials_lock:
                self.credentials.before_request(_BoundedAuthRequest(self.session), method, url, headers)
            with self.session.request(method, url, headers=headers, timeout=(10, 30),
                                      allow_redirects=False, stream=True, **kwargs) as response:
                if response.status_code == 404:
                    raise FileNotFoundError('Imagem não encontrada no Drive.')
                if not 200 <= response.status_code < 300:
                    raise DriveError('Google Drive indisponível ou sem acesso à pasta configurada.')
                declared = response.headers.get('Content-Length')
                if declared and int(declared) > limit:
                    raise DriveError('Resposta do Drive excede o limite permitido.')
                chunks = []; size = 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > limit:
                        raise DriveError('Resposta do Drive excede o limite permitido.')
                    chunks.append(chunk)
                return b''.join(chunks)
        except (DriveError, FileNotFoundError):
            raise
        except Exception:
            raise DriveError('Não foi possível acessar o Google Drive. Tente novamente mais tarde.') from None

    def put(self, area, filename, content):
        parent = self.folders.get(area)
        if not isinstance(parent, str) or not FILE_ID.fullmatch(parent):
            raise DriveError('Pasta do Google Drive não configurada para esta imagem.')
        boundary = 'cortae_' + uuid.uuid4().hex
        metadata = json.dumps({'name': filename, 'parents': [parent], 'mimeType': 'image/webp',
                               'appProperties': {'cortae_area': area}}, separators=(',', ':')).encode()
        body = (f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'.encode()
                + metadata + f'\r\n--{boundary}\r\nContent-Type: image/webp\r\n\r\n'.encode()
                + content + f'\r\n--{boundary}--\r\n'.encode())
        try:
            raw = self._request('POST', UPLOAD, params={'uploadType': 'multipart', 'fields': 'id', 'supportsAllDrives': 'true'},
                                headers={'Content-Type': f'multipart/related; boundary={boundary}'}, data=body)
        except FileNotFoundError:
            raise DriveError('Pasta de imagens indisponível no Google Drive. Verifique o acesso no servidor.') from None
        try:
            identifier = json.loads(raw)['id']
            if not FILE_ID.fullmatch(identifier):
                raise ValueError('id')
            return identifier
        except Exception:
            raise DriveError('Resposta inválida ao salvar imagem no Drive.') from None

    def get(self, identifier, max_bytes):
        if not FILE_ID.fullmatch(str(identifier)):
            raise DriveError('Referência de imagem inválida.')
        return self._request('GET', BASE + '/' + identifier, limit=max_bytes,
                             params={'alt': 'media', 'supportsAllDrives': 'true'})

    def publish_public(self, identifier):
        """Explicit reader permission for a newly uploaded public-area asset only.

        The transactional caller decides the area and checks private references.
        This method is never used by the anonymous reader or by private uploads.
        """
        if not FILE_ID.fullmatch(str(identifier)):
            raise DriveError('Referência de imagem inválida.')
        raw = self._request('POST', BASE + '/' + identifier + '/permissions',
                            params={'supportsAllDrives': 'true', 'fields': 'id,type,role,allowFileDiscovery'},
                            json={'type': 'anyone', 'role': 'reader', 'allowFileDiscovery': False})
        try:
            permission = json.loads(raw)
            if (not isinstance(permission.get('id'), str) or not permission['id']
                    or permission.get('type') != 'anyone' or permission.get('role') != 'reader'
                    or permission.get('allowFileDiscovery') is True):
                raise ValueError('permission')
            return permission['id']
        except Exception:
            raise DriveError('Não foi possível confirmar a leitura pública da imagem enviada.') from None

    def delete(self, identifier):
        if not FILE_ID.fullmatch(str(identifier)):
            raise DriveError('Referência de imagem inválida.')
        try:
            self._request('DELETE', BASE + '/' + identifier, params={'supportsAllDrives': 'true'})
        except FileNotFoundError:
            pass

    def trash(self, identifier):
        """Recoverable cleanup after a committed replacement or an explicit smoke test."""
        if not FILE_ID.fullmatch(str(identifier)):
            raise DriveError('Referência de imagem inválida.')
        try:
            self._request('PATCH', BASE + '/' + identifier,
                          params={'supportsAllDrives': 'true', 'fields': 'id,trashed'},
                          json={'trashed': True})
        except FileNotFoundError:
            pass


class PublicGoogleDriveStorage:
    """Read-only transport for individually published, registered Drive objects.

    No credentials, environment proxies, arbitrary URLs, cookies or login redirects.
    Image metadata and integrity are checked separately by image_storage.
    """
    name = PUBLIC_PROVIDER

    @staticmethod
    def _url(url, identifier):
        try:
            parsed = urlsplit(url)
            valid = {'drive.google.com': '/uc', 'drive.usercontent.google.com': '/download'}
            if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.fragment
                    or parsed.port not in (None, 443) or valid.get(parsed.hostname) != parsed.path
                    or parse_qs(parsed.query).get('id') != [identifier]):
                raise ValueError('url')
        except (ValueError, TypeError):
            raise DriveError('Redirecionamento de imagem pública não permitido.') from None
        return url

    def get(self, identifier, max_bytes):
        if not isinstance(identifier, str) or not FILE_ID.fullmatch(identifier):
            raise DriveError('Referência de imagem inválida.')
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or not 0 < max_bytes <= PUBLIC_MAX_BYTES:
            raise DriveError('Limite de imagem pública inválido.')
        url = 'https://drive.usercontent.google.com/download?' + urlencode({'id': identifier, 'export': 'download'})
        visited = set()
        try:
            with requests.Session() as session:
                session.trust_env = False
                session.auth = None
                session.headers.clear()
                session.proxies.clear()
                for _ in range(4):
                    self._url(url, identifier)
                    if url in visited:
                        raise DriveError('Redirecionamento de imagem pública inválido.')
                    visited.add(url)
                    session.cookies.clear()
                    with session.get(url, headers={'Accept': 'image/webp, application/octet-stream'},
                                     timeout=(10, 30), allow_redirects=False, stream=True) as response:
                        if response.status_code in (301, 302, 303, 307, 308):
                            location = response.headers.get('Location')
                            if not location:
                                raise DriveError('Redirecionamento de imagem pública inválido.')
                            url = self._url(urljoin(url, location), identifier)
                            continue
                        if response.status_code == 404:
                            raise FileNotFoundError('Imagem pública não encontrada no Drive.')
                        if response.status_code != 200:
                            raise DriveError('Imagem pública indisponível. Confira a permissão de leitura deste arquivo no Drive.')
                        mime = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
                        if mime not in {'image/webp', 'application/octet-stream', 'application/binary'}:
                            raise DriveError('O Drive não retornou uma imagem pública válida.')
                        declared = response.headers.get('Content-Length')
                        if declared is not None and (not declared.isdecimal() or int(declared) > max_bytes):
                            raise DriveError('Imagem pública excede o limite permitido.')
                        chunks = []; size = 0
                        for chunk in response.iter_content(65536):
                            size += len(chunk)
                            if size > max_bytes:
                                raise DriveError('Imagem pública excede o limite permitido.')
                            chunks.append(chunk)
                        return b''.join(chunks)
                raise DriveError('Excesso de redirecionamentos ao ler imagem pública.')
        except (DriveError, FileNotFoundError):
            raise
        except Exception:
            raise DriveError('Não foi possível ler a imagem pública no Google Drive.') from None
