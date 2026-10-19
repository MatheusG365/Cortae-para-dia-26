"""Administrative WAHA CLI. No database imports or sends during setup/status/QR."""
from runtime_check import require_supported_python
require_supported_python()

import argparse
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys

from waha_client import WahaClient, WahaError

PROJECT = Path(__file__).resolve().parents[1]


def save_qr(destination, payload):
    target = Path(destination).expanduser().resolve()
    if target == PROJECT or target.is_relative_to(PROJECT) or target.suffix.lower() != '.png':
        raise WahaError('Salve o QR em um arquivo .png fora do repositório.')
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise WahaError('O destino do QR já existe e foi preservado. Escolha outro arquivo.') from None
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            if sys.platform == 'win32':
                result = subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,text=True,check=True,timeout=10)
                sid = next(csv.reader(io.StringIO(result.stdout)))[1]
                if not re_sid(sid):
                    raise ValueError()
                subprocess.run(['icacls',str(target),'/reset'],capture_output=True,check=True,timeout=10)
                subprocess.run(['icacls',str(target),'/inheritance:r','/grant:r',f'*{sid}:(F)','*S-1-5-18:(F)'],capture_output=True,check=True,timeout=10)
            stream.write(payload)
        return target
    except Exception:
        target.unlink(missing_ok=True)
        raise WahaError('Não foi possível salvar o QR com acesso restrito.') from None


def re_sid(value):
    return value.startswith('S-1-') and all(part.isdigit() for part in value.split('-')[1:])


def load_settings():
    # config.py loads the server environment; main/application would import the DB.
    import config
    defaults = {'WAHA_ENABLED':False,'WAHA_BASE_URL':'http://127.0.0.1:3000',
        'WAHA_API_KEY':'','WAHA_SESSION':'default','WAHA_TIMEOUT':20}
    return {key:getattr(config,key,default) for key,default in defaults.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Administrar WAHA; status e pareamento não enviam mensagens.')
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('status','criar','iniciar','parar'):
        commands.add_parser(command)
    qr = commands.add_parser('qr'); qr.add_argument('--arquivo',required=True)
    send = commands.add_parser('enviar-texto',help='Envia uma mensagem real somente por execução explícita.')
    send.add_argument('--destino',required=True)
    send.add_argument('--texto',required=True)
    args = parser.parse_args(argv)
    try:
        with WahaClient(load_settings()) as client:
            if args.command == 'status':
                print(json.dumps(client.status(),ensure_ascii=False))
            elif args.command == 'qr':
                print('QR salvo com acesso restrito:',save_qr(args.arquivo,client.qr_png()))
            elif args.command == 'enviar-texto':
                client.send_text(args.destino,args.texto)
                print('Pedido de envio aceito pelo WAHA. Confirme a entrega no WhatsApp antes de repetir.')
            else:
                {'criar':client.create_session,'iniciar':client.start_session,'parar':client.stop_session}[args.command]()
                print('Operação de sessão concluída. Consulte status para verificar o pareamento.')
        return 0
    except (WahaError, OSError):
        # Never echo arbitrary OS/provider exceptions, which may contain secrets.
        error = sys.exception()
        print(str(error) if isinstance(error,WahaError) else 'Não foi possível concluir a operação local.',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
