"""Private Drive media transport. No sharing, public links or arbitrary URLs."""
import json
import hashlib
import re
import uuid
import threading
from collections import OrderedDict
from pathlib import Path

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
