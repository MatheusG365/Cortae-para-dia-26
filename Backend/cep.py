"""Bounded, anonymous postal-code lookup against the fixed ViaCEP service."""
import json
import re
import time
from collections import OrderedDict
from threading import Lock

import requests

UFS = frozenset('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())
MAX_RESPONSE_BYTES = 64 * 1024
CACHE_TTL = 600
CACHE_SIZE = 256
_cache = OrderedDict()
_cache_lock = Lock()


class CepErro(ValueError):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def normalizar(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{5}-?[0-9]{3}', value):
        raise CepErro('Informe um CEP com oito dígitos.', 400)
    return value.replace('-', '')


def _campo(data, field, limit, required=False):
    value = data.get(field, '')
    if not isinstance(value, str) or len(value) > limit or any(ord(char) < 32 for char in value):
        raise CepErro('A consulta de CEP está temporariamente indisponível.')
    value = value.strip()
    if required and not value:
        raise CepErro('A consulta de CEP está temporariamente indisponível.')
    return value


def consultar(value):
    postal_code = normalizar(value)
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(postal_code)
        if cached and cached[0] > now:
            _cache.move_to_end(postal_code)
            return dict(cached[1])
        _cache.pop(postal_code, None)
    try:
        # Do not inherit proxy settings, .netrc credentials or cookies. The only
        # customer input sent to this fixed HTTPS host is the validated CEP.
        with requests.Session() as session:
            session.trust_env = False
            with session.get('https://viacep.com.br/ws/' + postal_code + '/json/',
                             timeout=(3, 5), allow_redirects=False, stream=True,
                             headers={'Accept': 'application/json'}) as response:
                if response.status_code != 200:
                    raise CepErro('A consulta de CEP está temporariamente indisponível.')
                content = bytearray()
                for chunk in response.iter_content(chunk_size=8192):
                    content.extend(chunk)
                    if len(content) > MAX_RESPONSE_BYTES:
                        raise CepErro('A consulta de CEP está temporariamente indisponível.')
                data = json.loads(content.decode('utf-8'))
        if not isinstance(data, dict):
            raise CepErro('A consulta de CEP está temporariamente indisponível.')
        if data.get('erro') in (True, 'true'):
            raise CepErro('CEP não encontrado.', 404)
        if normalizar(data.get('cep')) != postal_code:
            raise CepErro('A consulta de CEP está temporariamente indisponível.')
        result = {'cep': postal_code,
                  'logradouro': _campo(data, 'logradouro', 160),
                  'bairro': _campo(data, 'bairro', 100),
                  'cidade': _campo(data, 'localidade', 100, True),
                  'uf': _campo(data, 'uf', 2, True)}
        if result['uf'] not in UFS:
            raise CepErro('A consulta de CEP está temporariamente indisponível.')
    except CepErro as exc:
        # A malformed provider CEP is a provider failure, not a client error.
        if exc.status == 400:
            raise CepErro('A consulta de CEP está temporariamente indisponível.') from None
        raise
    except (requests.RequestException, ValueError, UnicodeError, TypeError):
        raise CepErro('A consulta de CEP está temporariamente indisponível.') from None
    with _cache_lock:
        _cache[postal_code] = (time.monotonic() + CACHE_TTL, dict(result))
        _cache.move_to_end(postal_code)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return result
