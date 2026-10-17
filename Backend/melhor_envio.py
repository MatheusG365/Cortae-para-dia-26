"""Melhor Envio server client. Never receives login passwords or browser credentials."""
import json
import urllib.request
import urllib.error
from application import app

class EntregaErro(Exception):
    def __init__(self,texto,status=502):super().__init__(texto);self.status=status

def configurado():return bool(app.config.get('MELHOR_ENVIO_TOKEN'))

def chamar(metodo,caminho,corpo=None):
    token=app.config.get('MELHOR_ENVIO_TOKEN')
    if not token:raise EntregaErro('Melhor Envio não configurado. Configure o token de API no servidor.',503)
    agent=app.config.get('MELHOR_ENVIO_USER_AGENT')
    if not agent or '@' not in agent:
        email=app.config.get('MAIL_USER')
        if not email:raise EntregaErro('Configure o contato técnico MELHOR_ENVIO_USER_AGENT no servidor.',503)
        agent='Cortae ('+email+')'
    sandbox=app.config.get('MELHOR_ENVIO_SANDBOX',False)
    base='https://sandbox.melhorenvio.com.br' if sandbox else 'https://melhorenvio.com.br'
    req=urllib.request.Request(base+(caminho if caminho.startswith('/api/v2/') else '/api/v2/me/shipment/'+caminho),
        data=json.dumps(corpo).encode() if corpo is not None else None,method=metodo,
        headers={'Authorization':'Bearer '+token,'Accept':'application/json','Content-Type':'application/json',
                 'User-Agent':agent})
    try:
        with urllib.request.urlopen(req,timeout=25) as response:result=json.loads(response.read(2*1024*1024).decode())
    except urllib.error.HTTPError as exc:
        # Provider bodies may expose documents/tokens; never echo them.
        raise EntregaErro('Melhor Envio recusou a operação. Confira a configuração e os dados do envio.',503 if exc.code in (401,403) else 502) from None
    except (urllib.error.URLError,TimeoutError,ValueError):raise EntregaErro('Resposta do Melhor Envio indisponível. Operações financeiras incertas exigem conferência manual.',502) from None
    return result

def calcular(origem,destino,produtos):
    return chamar('POST','calculate',{'from':{'postal_code':origem},'to':{'postal_code':destino},'products':produtos})

