"""Read-only Firebird build/ODS checks and fresh portable-runtime bootstrap."""
from runtime_check import require_supported_python

require_supported_python()

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import firebirdsql
from firebirdsql import services
from firebirdsql.consts import ISOLATION_LEVEL_READ_COMMITED_RO
from dotenv import dotenv_values

EXPECTED_VERSION = '4.0.4.3010'
EXPECTED_ODS = (13, 0)
BASE = Path(__file__).resolve().parent


class FirebirdRuntimeError(RuntimeError):
    pass


def _cleanup(resource, method):
    if resource is not None:
        try:
            getattr(resource, method)()
        except Exception:
            # Cleanup must not expose driver details or hide the safe error.
            pass


def settings():
    values = {**dotenv_values(BASE / '.env'), **os.environ}
    host = values.get('DB_HOST') or 'localhost'
    port = values.get('DB_PORT') or '3054'
    common = dict(host=host, port=int(port), user=values.get('DB_USER') or 'SYSDBA',
                  password=values.get('DB_PASSWORD') or '', timeout=10, charset='UTF8')
    main = {**common, 'database': values.get('DB_NAME') or str(BASE / 'CORTAE.FDB')}
    log = {**common, 'host': values.get('LOG_DB_HOST') or host,
           'port': int(values.get('LOG_DB_PORT') or port),
           'user': values.get('LOG_DB_USER') or common['user'],
           'password': values.get('LOG_DB_PASSWORD') or common['password'],
           'database': values.get('LOG_DB_NAME') or str(BASE / 'LOG_CORTAE.FDB')}
    return main, log


def check_server(options):
    connection = None
    try:
        connection = services.connect(**{key: value for key, value in options.items() if key != 'database'})
        version = connection.getServerVersion()
        architecture = connection.getArchitecture()
        if not re.search(r'(?<![0-9])4\.0\.4\.3010(?![0-9])', version):
            raise FirebirdRuntimeError('Servidor exige Firebird exato 4.0.4.3010; versão encontrada incompatível.')
        arch = architecture.lower()
        if ('windows' not in arch or not any(label in arch for label in ('x86', 'win32', '32-bit', 'i386', 'i486', 'i586', 'i686')) or
                any(label in arch for label in ('x64', 'amd64', 'x86_64', '64-bit'))):
            raise FirebirdRuntimeError('Servidor exige Firebird Windows x86 de 32 bits.')
        return dict(version=version, architecture=architecture)
    except FirebirdRuntimeError:
        raise
    except Exception:
        raise FirebirdRuntimeError('Não foi possível verificar o Firebird. Confira host, porta, usuário e senha privados no servidor.') from None
    finally:
        _cleanup(connection, 'close')


def check_database(options):
    server = check_server(options)
    connection = cursor = None
    try:
        connection = firebirdsql.connect(**options, isolation_level=ISOLATION_LEVEL_READ_COMMITED_RO)
        cursor = connection.cursor()
        cursor.execute('SELECT MON$ODS_MAJOR,MON$ODS_MINOR FROM MON$DATABASE')
        ods = tuple(cursor.fetchone())
        if ods != EXPECTED_ODS:
            raise FirebirdRuntimeError('Banco exige ODS 13.0 do Firebird 4. Não substitua arquivos ativos: faça backup e restauração verificada em cópias.')
        return {**server, 'ods': list(ods)}
    except FirebirdRuntimeError:
        raise
    except Exception:
        raise FirebirdRuntimeError('Banco indisponível ou incompatível com Firebird 4. Faça backup e restauração verificada; nenhuma migração automática será executada.') from None
    finally:
        _cleanup(connection, 'rollback')
        _cleanup(cursor, 'close')
        _cleanup(connection, 'close')


def initialize_home(home):
    """Only the installer-created pending marker permits initial SYSDBA creation."""
    home = Path(home).resolve()
    marker = home / '.cortae-init-pending.json'
    if not marker.is_file():
        raise FirebirdRuntimeError('Instalação existente preservada; inicialização automática não autorizada.')
    data = json.loads(marker.read_text(encoding='utf-8-sig'))
    if data.get('owner') != 'Cortae' or data.get('version') != EXPECTED_VERSION or data.get('phase') != 'fresh':
        raise FirebirdRuntimeError('Inicialização anterior interrompida. Confira manualmente a instalação; a senha existente não será alterada.')
    main, _ = settings()
    password = main['password']
    if main['user'].upper() != 'SYSDBA' or not password or any(ch in password for ch in ('\r', '\n', '\0')):
        raise FirebirdRuntimeError('Preencha DB_USER=SYSDBA e DB_PASSWORD em Backend/.env e execute Configurar-Cortae.cmd novamente.')
    # Claim before invoking isql. After a crash, never reset an existing password.
    marker.write_text(json.dumps({**data, 'phase': 'initializing'}), encoding='utf-8')
    sql = "CREATE USER SYSDBA PASSWORD '" + password.replace("'", "''") + "';\nCOMMIT;\nQUIT;\n"
    try:
        result = subprocess.run([str(home / 'isql.exe'), '-b', '-q', '-user', 'SYSDBA', 'employee'],
            input=sql, capture_output=True, text=True, cwd=home, timeout=30,
            env={**os.environ, 'FIREBIRD': str(home)}, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise FirebirdRuntimeError('Não foi possível inicializar SYSDBA. Consulte doc/README.security_database.txt do runtime; saída privada omitida.')
        marker.unlink()
        (home / '.cortae-initialized').write_text(EXPECTED_VERSION, encoding='ascii')
    except FirebirdRuntimeError:
        raise
    except Exception:
        raise FirebirdRuntimeError('Inicialização interrompida. Confira manualmente o runtime antes de iniciar; senha existente preservada.') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description='Conferir Firebird exato e ODS, sem migração ou alterações de esquema.')
    parser.add_argument('--server-only', action='store_true')
    parser.add_argument('--initialize-home')
    args = parser.parse_args(argv)
    try:
        if args.initialize_home:
            initialize_home(args.initialize_home)
            print('Conta SYSDBA inicializada na instalação nova do projeto.')
        else:
            check = check_server if args.server_only else check_database
            print(json.dumps({'firebird': EXPECTED_VERSION, 'databases': [check(options) for options in settings()]}))
        return 0
    except (FirebirdRuntimeError, ValueError):
        # Do not include connection objects, subprocess stderr or credentials.
        print(str(sys.exception()) if isinstance(sys.exception(), FirebirdRuntimeError)
              else 'Configuração de host ou porta inválida.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
