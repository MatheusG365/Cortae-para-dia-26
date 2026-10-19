"""Server-side Google Drive setup; never imports the app or opens Firebird.

OAuth secrets and refresh tokens remain in a private file outside this project.
The optional upload check creates one synthetic file and moves only it to Trash.
"""
from runtime_check import require_supported_python

require_supported_python()

import argparse
from contextlib import contextmanager
import csv
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import logging
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qs, urlsplit
import uuid
import webbrowser

from google_drive_storage import BASE, FILE_ID, GoogleDriveStorage, DriveError, SCOPE

PROJECT = Path(__file__).resolve().parent.parent
AREAS = ('perfil', 'barbearia', 'marketplace', 'visagismo/cortes',
         'visagismo/fotos', 'visagismo/resultados', 'site', 'mobile')
FULL_SCOPE = 'https://www.googleapis.com/auth/drive'
FOLDER_MIME = 'application/vnd.google-apps.folder'


class SetupError(Exception):
    """A safe explanation that contains no OAuth codes, tokens or provider body."""


def external_path(value, *, existing=False):
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise SetupError('Informe um caminho absoluto fora da pasta do projeto.')
    if path.is_symlink():
        raise SetupError('Não use links para arquivos de autorização.')
    resolved = path.resolve()
    if resolved.is_relative_to(PROJECT):
        raise SetupError('Credenciais e configuração privada devem ficar fora do projeto.')
    if existing and (not resolved.is_file() or resolved.stat().st_size > 65536 or resolved.stat().st_nlink != 1):
        raise SetupError('Arquivo local inválido, ausente ou grande demais.')
    return resolved


def _load_json(path):
    try:
        result = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except (OSError, ValueError):
        raise SetupError('Não foi possível ler o arquivo JSON local informado.') from None


def _restrict_file(path):
    """Restrict a newly created empty file before writing any secrets."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size:
        raise SetupError('As permissões só podem ser preparadas em um novo arquivo vazio.')
    if sys.platform == 'win32':
        try:
            identity = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                                      capture_output=True, text=True, check=True, timeout=10)
            sid = next(csv.reader(io.StringIO(identity.stdout)))[1]
            if not sid.startswith('S-1-') or not all(part.isdigit() for part in sid.split('-')[1:]):
                raise ValueError()
            # mkstemp can create explicit ACL entries. Reset only this empty file,
            # then replace inherited access before any credential bytes are written.
            subprocess.run(['icacls', str(path), '/reset'],
                           capture_output=True, check=True, timeout=10)
            subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                            f'*{sid}:(F)', '*S-1-5-18:(F)'], capture_output=True, check=True, timeout=10)
        except (OSError, ValueError, IndexError, StopIteration, subprocess.SubprocessError):
            raise SetupError('Não foi possível restringir o arquivo de credenciais ao usuário do servidor.') from None
    else:
        os.chmod(path, 0o600)


def save_credentials(destination, payload, *, replace=False):
    target = external_path(destination)
    if target.exists():
        if not replace:
            raise SetupError('Já existe uma credencial nesse caminho. Use outro destino ou --substituir-credencial.')
        external_path(target, existing=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.cortae-oauth-', suffix='.tmp', dir=target.parent)
    temporary = Path(temporary)
    try:
        os.close(descriptor)
        _restrict_file(temporary)
        with temporary.open('w', encoding='utf-8', newline='\n') as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, target)
        else:
            try:
                os.link(temporary, target)
            except FileExistsError:
                raise SetupError('O destino foi ocupado durante a autorização. A credencial existente foi preservada.') from None
    finally:
        temporary.unlink(missing_ok=True)
    return target


class _PrivateServer(HTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if sys.platform == 'win32' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


@contextmanager
def _quiet_oauth_logs():
    previous = logging.root.manager.disable
    try:
        # OAuth libraries may log callback URLs, request bodies and headers in DEBUG.
        # This CLI never needs those logs; disable all transient OAuth logging.
        logging.disable(logging.CRITICAL)
        yield
    finally:
        logging.disable(previous)


def authorize(client_file, destination, *, full_access=False, replace=False, timeout=300):
    from google_auth_oauthlib.flow import InstalledAppFlow
    client_path = external_path(client_file, existing=True)
    target = external_path(destination)
    if target.exists() and not replace:
        raise SetupError('O arquivo de autorização já existe. Ele não será substituído automaticamente.')
    info = _load_json(client_path)
    installed = info.get('installed')
    if not isinstance(installed, dict) or 'web' in info:
        raise SetupError('Baixe um cliente OAuth do tipo Aplicativo para computador (Desktop).')
    if installed.get('auth_uri') not in {'https://accounts.google.com/o/oauth2/auth', 'https://accounts.google.com/o/oauth2/v2/auth'} \
            or installed.get('token_uri') != 'https://oauth2.googleapis.com/token' \
            or not str(installed.get('client_id', '')).endswith('.apps.googleusercontent.com') \
            or not isinstance(installed.get('client_secret'), str) or not installed['client_secret']:
        raise SetupError('O JSON não contém um cliente OAuth Desktop válido do Google.')
    scopes = [FULL_SCOPE if full_access else SCOPE]
    state = secrets.token_urlsafe(32)
    result = {}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log the URL: it contains the short-lived OAuth code.

        def do_GET(self):
            try:
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query, max_num_fields=10)
                valid = (parsed.path == '/' and len(query.get('state', [])) == 1
                         and secrets.compare_digest(query['state'][0], state))
            except (ValueError, TypeError):
                valid = False
            if not valid:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Solicitacao invalida.')
                return
            code = query.get('code', [])
            if len(code) == 1 and 0 < len(code[0]) <= 4096:
                result['code'] = code[0]
                message = 'Autorização recebida. Volte ao terminal para verificar o resultado.'
            else:
                result['error'] = True
                message = 'Autorização não concluída. Volte ao terminal.'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(message.encode('utf-8'))
    try:
        with _quiet_oauth_logs():
            flow = InstalledAppFlow.from_client_config(info, scopes=scopes, autogenerate_code_verifier=True)
            flow.oauth2session.trust_env = False
            with _PrivateServer(('127.0.0.1', 0), Callback) as server:
                flow.redirect_uri = f'http://127.0.0.1:{server.server_port}/'
                authorization_url, _ = flow.authorization_url(access_type='offline', prompt='consent', state=state)
                if not webbrowser.open(authorization_url, new=1, autoraise=True):
                    raise SetupError('Não foi possível abrir o navegador padrão para a autorização.')
                server.timeout = 0.5
                deadline = time.monotonic() + max(1, min(int(timeout), 600))
                while not result and time.monotonic() < deadline:
                    server.handle_request()
                if not result or result.get('error'):
                    raise SetupError('Autorização cancelada ou tempo esgotado. Nenhuma credencial foi salva.')
                flow.fetch_token(code=result.pop('code'), timeout=(10, 30), allow_redirects=False)
                credentials = flow.credentials
                granted = getattr(credentials, 'granted_scopes', None)
                if isinstance(granted, str):
                    granted = granted.split()
                if granted is not None and not set(scopes).issubset(set(granted)):
                    raise SetupError('O escopo solicitado não foi autorizado. Nenhuma credencial foi salva.')
                if not credentials.refresh_token:
                    raise SetupError('O Google não retornou autorização de acesso contínuo. Nenhuma credencial foi salva.')
                payload = json.loads(credentials.to_json())
                payload['type'] = 'authorized_user'
                payload['scopes'] = scopes
                payload['token_uri'] = 'https://oauth2.googleapis.com/token'
                return save_credentials(target, payload, replace=replace)
    except SetupError:
        raise
    except Exception:
        raise SetupError('Não foi possível concluir a autorização OAuth. Confira o cliente Desktop, o usuário de teste e o consentimento no Google.') from None


def load_config(*, credentials=None, folders_file=None):
    # Config only reads server environment; importing main/application would run DB work.
    import config
    settings = {key: getattr(config, key, '') for key in (
        'GOOGLE_DRIVE_CREDENTIALS_JSON', 'GOOGLE_DRIVE_CREDENTIALS_FILE', 'GOOGLE_DRIVE_FOLDER_IDS',
        'GOOGLE_DRIVE_FOLDER_IDS_FILE', 'GOOGLE_DRIVE_SHARED_DRIVE_ID')}
    if credentials:
        settings['GOOGLE_DRIVE_CREDENTIALS_JSON'] = ''
        settings['GOOGLE_DRIVE_CREDENTIALS_FILE'] = str(external_path(credentials, existing=True))
    if folders_file:
        settings['GOOGLE_DRIVE_FOLDER_IDS_FILE'] = str(external_path(folders_file, existing=True))
    return settings


def verify_storage(settings, root_id=None):
    """Inspect the configured private folder tree without changing any file."""
    provider = GoogleDriveStorage(settings)
    root_id = root_id or provider.folders.get('root')
    if not isinstance(root_id, str) or not FILE_ID.fullmatch(root_id):
        raise SetupError('Informe --pasta-raiz com o ID da pasta principal já criada.')
    folder_ids = [provider.folders.get(area) for area in AREAS]
    if any(not isinstance(value, str) or not FILE_ID.fullmatch(value) for value in folder_ids):
        raise SetupError(f'O mapa precisa conter as {len(AREAS)} áreas de imagem com IDs válidos.')
    if len(set(folder_ids)) != len(AREAS) or root_id in folder_ids:
        raise SetupError('Cada área deve apontar para sua própria subpasta da pasta principal.')
    cache = {}
    def metadata(identifier):
        if identifier not in cache:
            try:
                raw = provider._request('GET', BASE+'/'+identifier,
                                        params={'supportsAllDrives': 'true',
                                                'fields': 'id,mimeType,parents,trashed,driveId,capabilities(canAddChildren)'})
                item = json.loads(raw)
            except (FileNotFoundError, DriveError, ValueError):
                raise SetupError('O aplicativo OAuth não consegue ler uma das pastas configuradas. Confira o consentimento e o mapa; nenhuma pasta foi criada.') from None
            if item.get('id') != identifier or item.get('mimeType') != FOLDER_MIME or item.get('trashed') is not False:
                raise SetupError('O mapa contém um item que não é uma pasta ativa do Drive.')
            cache[identifier] = item
        return cache[identifier]
    metadata(root_id)
    for area, identifier in zip(AREAS, folder_ids):
        item = metadata(identifier)
        if item.get('capabilities', {}).get('canAddChildren') is not True:
            raise SetupError('A autorização atual não permite adicionar imagens em todas as pastas configuradas.')
        expected_shared = settings.get('GOOGLE_DRIVE_SHARED_DRIVE_ID')
        if expected_shared and item.get('driveId') != expected_shared:
            raise SetupError('Uma pasta está fora do Drive compartilhado configurado.')
        pending = [(identifier, 0)]
        visited = set()
        found = False
        while pending:
            current, depth = pending.pop()
            if current == root_id:
                found = True
                break
            if current in visited or depth >= 8:
                continue
            visited.add(current)
            parents = metadata(current).get('parents', [])
            if not isinstance(parents, list) or len(parents) > 5:
                raise SetupError('Estrutura de pastas inesperada no Drive.')
            for parent in parents:
                if not isinstance(parent, str) or not FILE_ID.fullmatch(parent):
                    raise SetupError('Estrutura de pastas inesperada no Drive.')
                pending.append((parent, depth + 1))
        if not found:
            raise SetupError(f'A pasta da área {area} não pertence à pasta principal configurada.')
    return provider


def test_upload(settings, root_id=None):
    """One synthetic file, SHA-256 check, and recoverable Trash cleanup only."""
    from PIL import Image
    provider = verify_storage(settings, root_id)
    content = io.BytesIO()
    Image.new('RGB', (8, 8), (237, 135, 25)).save(content, format='WEBP', quality=70)
    data = content.getvalue()
    name = 'cortae-teste-'+uuid.uuid4().hex+'.webp'
    created = None
    try:
        created = provider.put('perfil', name, data)
        retrieved = provider.get(created, len(data))
        if hashlib.sha256(data).digest() != hashlib.sha256(retrieved).digest():
            raise SetupError('O conteúdo recebido não corresponde à imagem sintética enviada.')
    finally:
        if created:
            try:
                provider.trash(created)
            except Exception:
                raise SetupError(f'O arquivo de teste {name} foi criado, mas não pôde ser movido à lixeira. Remova somente esse arquivo de teste manualmente.') from None
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description='Configuração privada das imagens no Google Drive. Não acessa o banco de dados.')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--autorizar', action='store_true', help='Abrir o consentimento OAuth Desktop no navegador do servidor.')
    action.add_argument('--verificar', action='store_true', help='Somente ler e validar as pastas já configuradas.')
    action.add_argument('--teste-envio', action='store_true', help='Enviar uma imagem sintética, conferir a leitura e mover esse teste à lixeira.')
    parser.add_argument('--cliente-oauth', help='Caminho absoluto do JSON Desktop baixado do Google, fora do projeto.')
    default_output = Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local'/'share'))/'Cortae'/'google-drive'/'authorized_user.json'
    parser.add_argument('--credenciais', help='Arquivo privado authorized_user; padrão fica fora do projeto.')
    parser.add_argument('--pastas', help='Caminho absoluto do mapa JSON local com os IDs das pastas existentes.')
    parser.add_argument('--pasta-raiz', help='ID da pasta principal existente; pode ser também a chave root do mapa.')
    parser.add_argument('--acesso-drive-completo', action='store_true', help='Solicitar explicitamente o escopo amplo Drive para pastas pré-existentes criadas por outro aplicativo.')
    parser.add_argument('--substituir-credencial', action='store_true', help='Substituir uma credencial local existente após novo consentimento.')
    args = parser.parse_args(argv)
    try:
        if args.autorizar:
            if not args.cliente_oauth:
                raise SetupError('Informe --cliente-oauth com o JSON Desktop baixado do Google.')
            authorize(args.cliente_oauth, args.credenciais or str(default_output), full_access=args.acesso_drive_completo,
                      replace=args.substituir_credencial)
            print('Autorização salva no arquivo privado informado. Execute --verificar antes de habilitar os uploads.')
        else:
            if args.acesso_drive_completo or args.substituir_credencial or args.cliente_oauth:
                raise SetupError('As opções de consentimento só são usadas junto de --autorizar.')
            settings = load_config(credentials=args.credenciais, folders_file=args.pastas)
            if args.teste_envio:
                test_upload(settings, args.pasta_raiz)
                print('Teste aprovado: WebP enviado, conteúdo verificado e somente o arquivo sintético movido à lixeira.')
            else:
                verify_storage(settings, args.pasta_raiz)
                print(f'Verificação aprovada: {len(AREAS)} áreas acessíveis, graváveis e pertencentes à pasta principal.')
        return 0
    except (SetupError, DriveError, FileNotFoundError) as error:
        print('Configuração não concluída: '+str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Operação cancelada. Nenhuma credencial foi exibida.', file=sys.stderr)
        return 130
    except Exception:
        print('Não foi possível concluir a configuração. Confira os arquivos locais e a autorização do Google.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
