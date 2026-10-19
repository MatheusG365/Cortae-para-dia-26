"""Server-side WAHA client. No Flask imports, background sends or automatic retries."""
import ipaddress
import json
import math
import re
from urllib.parse import urlsplit

import requests

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
SESSION_NAME = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')


class WahaError(RuntimeError):
    """Public errors deliberately exclude provider bodies, URLs and credentials."""


class WahaClient:
    def __init__(self, settings):
        enabled = settings.get('WAHA_ENABLED', False)
        self.enabled = enabled is True or isinstance(enabled, str) and enabled.lower() in ('true', '1', 'yes', 'sim')
        self._transport = None
        if not self.enabled:
            return
        base = settings.get('WAHA_BASE_URL', 'http://127.0.0.1:3000')
        self._key = settings.get('WAHA_API_KEY', '')
        self.session = settings.get('WAHA_SESSION', 'default')
        try:
            parsed = urlsplit(base)
            port = parsed.port
            hostname = parsed.hostname
            loopback = hostname == 'localhost'
            if hostname and not loopback:
                try:
                    loopback = ipaddress.ip_address(hostname).is_loopback
                except ValueError:
                    pass
            valid = (parsed.scheme in ('http', 'https') and hostname and parsed.netloc
                     and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                     and parsed.path in ('', '/') and (parsed.scheme == 'https' or loopback)
                     and not any(ch.isspace() or ord(ch) < 32 for ch in base)
                     and (port is None or 1 <= port <= 65535))
        except (ValueError, TypeError, AttributeError):
            valid = False
        if not valid:
            raise WahaError('Configure WAHA_BASE_URL com origem HTTPS ou HTTP loopback, sem credenciais ou caminho.')
        if not isinstance(self._key, str) or not self._key or len(self._key) > 4096 \
                or any(ord(ch) < 33 or ord(ch) > 126 for ch in self._key):
            raise WahaError('Configure WAHA_API_KEY no servidor com a chave original, sem espaços ou quebras de linha.')
        if self._key.startswith('sha512:'):
            raise WahaError('WAHA_API_KEY do cliente exige a chave original, não seu hash SHA-512.')
        if not isinstance(self.session, str) or not SESSION_NAME.fullmatch(self.session):
            raise WahaError('WAHA_SESSION deve conter de 1 a 64 letras, números, hífen ou sublinhado.')
        try:
            timeout = settings.get('WAHA_TIMEOUT', 20)
            if isinstance(timeout, bool):
                raise ValueError()
            self.timeout = float(timeout)
            if not math.isfinite(self.timeout) or not 1 <= self.timeout <= 120:
                raise ValueError()
        except (TypeError, ValueError):
            raise WahaError('WAHA_TIMEOUT deve ficar entre 1 e 120 segundos.') from None
        self._base = base.rstrip('/')

    def _request(self, method, path, payload=None, *, png=False):
        if not self.enabled:
            raise WahaError('WhatsApp desativado. Configure WAHA_ENABLED=true no servidor.')
        if self._transport is None:
            self._transport = requests.Session()
            self._transport.trust_env = False
        response = None
        try:
            response = self._transport.request(method, self._base + path, json=payload,
                headers={'X-Api-Key':self._key, 'Accept':'image/png' if png else 'application/json'},
                timeout=(min(5, self.timeout), self.timeout), allow_redirects=False, stream=True)
            if not 200 <= response.status_code < 300:
                raise WahaError(f'WAHA recusou a operação (HTTP {response.status_code}). Confira o serviço, a chave e a sessão.')
            parts = []; size = 0
            for part in response.iter_content(chunk_size=65536):
                size += len(part)
                if size > MAX_RESPONSE_BYTES:
                    raise WahaError('Resposta WAHA excedeu o limite permitido.')
                parts.append(part)
            raw = b''.join(parts)
            if png:
                if response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'image/png' or not raw.startswith(PNG_SIGNATURE):
                    raise WahaError('WAHA não retornou um QR em PNG válido. Confira o estado da sessão.')
                return raw
            if not raw and response.status_code == 204:
                return {}
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise WahaError('WAHA retornou um objeto JSON inválido.')
            return data
        except requests.RequestException:
            suffix = ' O envio pode ter sido aceito; confira antes de repetir.' if path == '/api/sendText' else ''
            raise WahaError('Não foi possível comunicar com WAHA.' + suffix) from None
        except (ValueError, UnicodeError):
            raise WahaError('WAHA retornou uma resposta inválida.') from None
        finally:
            if response is not None:
                response.close()

    def status(self):
        self._require_enabled()
        data = self._request('GET', f'/api/sessions/{self.session}')
        name, status = data.get('name'), data.get('status')
        if name != self.session or not isinstance(status, str) or not re.fullmatch(r'[A-Z_]{1,40}', status):
            raise WahaError('WAHA retornou estado de sessão inválido.')
        return {'name':name, 'status':status, 'connected':status == 'WORKING'}

    def _require_enabled(self):
        if not self.enabled:
            raise WahaError('WhatsApp desativado. Configure WAHA_ENABLED=true no servidor.')

    def create_session(self):
        self._require_enabled()
        return self._request('POST', '/api/sessions', {'name':self.session, 'start':False})

    def start_session(self):
        self._require_enabled()
        return self._request('POST', f'/api/sessions/{self.session}/start')

    def stop_session(self):
        self._require_enabled()
        return self._request('POST', f'/api/sessions/{self.session}/stop')

    def qr_png(self):
        self._require_enabled()
        return self._request('GET', f'/api/{self.session}/auth/qr', png=True)

    def send_text(self, recipient, text):
        self._require_enabled()
        if not isinstance(recipient, str):
            raise WahaError('Informe um telefone internacional com DDI e DDD, sem pontuação.')
        number = recipient.removeprefix('+').removesuffix('@c.us')
        if not re.fullmatch(r'[1-9][0-9]{7,14}', number):
            raise WahaError('Informe um telefone internacional com DDI e DDD, sem pontuação.')
        if not isinstance(text, str) or not text.strip() or len(text) > 4096:
            raise WahaError('O texto deve conter de 1 a 4096 caracteres.')
        return self._request('POST', '/api/sendText', {'session':self.session, 'chatId':number+'@c.us', 'text':text})

    def close(self):
        if self._transport is not None:
            self._transport.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
