import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

load_dotenv(
    os.path.join(BASE_DIR, '.env'),
    override=False
)


# ==========================================================
# SEGURANÇA
# ==========================================================

SECRET_KEY = os.getenv('SECRET_KEY')

DEBUG = os.getenv('DEBUG', 'false').lower() in ('1', 'true', 'sim', 'yes')
STARTUP_MIGRATIONS = os.getenv('STARTUP_MIGRATIONS', 'true').lower() in ('1', 'true', 'sim', 'yes')
PORT = int(os.getenv('PORT', '5000'))
API_HOST = os.getenv('API_HOST', '0.0.0.0').strip() or '0.0.0.0'
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', str(85 * 1024 * 1024)))


# ==========================================================
# DIRETÓRIO PRINCIPAL DO BACKEND
# ==========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# ==========================================================
# FIREBIRD
# ==========================================================

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '3050'))
DB_TIMEOUT = int(os.getenv('DB_TIMEOUT', '10'))

DB_NAME = os.getenv('DB_NAME', os.path.join(BASE_DIR, 'CORTAE.FDB'))

DB_USER = os.getenv('DB_USER', 'SYSDBA')

DB_PASSWORD = os.getenv('DB_PASSWORD')


# ==========================================================
# FIREBIRD - BANCO DE LOG/AUDITORIA (SEPARADO)
# ==========================================================
# Se o arquivo tiver outro nome/local, defina LOG_DB_NAME no .env.
# Exemplo Windows:
# LOG_DB_NAME=C:\\bancos\\CORTAE_LOG.FDB

LOG_DB_HOST = os.getenv('LOG_DB_HOST', DB_HOST)
LOG_DB_PORT = int(os.getenv('LOG_DB_PORT', str(DB_PORT)))
LOG_DB_NAME = os.getenv(
    'LOG_DB_NAME',
    os.path.join(BASE_DIR, 'LOG_CORTAE.FDB')
)
LOG_DB_USER = os.getenv('LOG_DB_USER', DB_USER)
LOG_DB_PASSWORD = os.getenv('LOG_DB_PASSWORD', DB_PASSWORD)
LOG_DB_TABLE = os.getenv('LOG_DB_TABLE', 'LOG_ALTERACAO')

# False: se o banco de LOG estiver fora do ar, a ação principal continua e o
# erro aparece no terminal. True propaga a falha de auditoria para a rota.
# Como são dois bancos separados, isso NÃO cria uma transação distribuída/atômica.
LOG_OBRIGATORIO = os.getenv('LOG_OBRIGATORIO', 'false').lower() in ('1', 'true', 'sim', 'yes')


# ==========================================================
# EMAIL - GMAIL
# ==========================================================

MAIL_USER = os.getenv('MAIL_USER')

MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')


# ==========================================================
# SMTP
# ==========================================================

MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')

MAIL_PORT = int(os.getenv('MAIL_PORT', '465'))


# ==========================================================
# UPLOADS
# ==========================================================

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    'uploads'
)


# ==========================================================
# FOTOS DE PERFIL
# ==========================================================

PERFIL_FOLDER = os.path.join(
    UPLOAD_FOLDER,
    'perfil'
)

# New runtime uploads use private Google Drive media. Missing credentials fail
# explicitly; selecting local is only an intentional development setting.
IMAGE_STORAGE_PROVIDER = os.getenv('IMAGE_STORAGE_PROVIDER', 'google_drive').strip().lower()
GOOGLE_DRIVE_CREDENTIALS_FILE = os.getenv('GOOGLE_DRIVE_CREDENTIALS_FILE', '').strip()
GOOGLE_DRIVE_FOLDER_IDS = os.getenv('GOOGLE_DRIVE_FOLDER_IDS', '{}').strip()
GOOGLE_DRIVE_FOLDER_IDS_FILE = os.getenv('GOOGLE_DRIVE_FOLDER_IDS_FILE', '').strip()
GOOGLE_DRIVE_SHARED_DRIVE_ID = os.getenv('GOOGLE_DRIVE_SHARED_DRIVE_ID', '').strip()
IMAGE_LOCAL_FOLDER = os.getenv('IMAGE_LOCAL_FOLDER', os.path.join(UPLOAD_FOLDER, '.managed'))


# ==========================================================
# VISAGISMO
# ==========================================================
# Configure a chave apenas pelo ambiente do servidor, nunca no repositório.
def _limpar_env(nome, padrao=None):
    valor = os.getenv(nome, padrao)
    if valor is None:
        return None
    valor = valor.strip().strip('"').strip("'").strip()
    return valor or None


OPENAI_API_KEY = _limpar_env('OPENAI_API_KEY')
VISAGISMO_ANALYSIS_MODEL = os.getenv('VISAGISMO_ANALYSIS_MODEL', 'gpt-5.6-terra')
VISAGISMO_IMAGE_MODEL = os.getenv('VISAGISMO_IMAGE_MODEL', 'gpt-image-2')
VISAGISMO_IMAGE_QUALITY = os.getenv('VISAGISMO_IMAGE_QUALITY', 'medium')
VISAGISMO_FOLDER = os.path.join(UPLOAD_FOLDER, 'visagismo')
VISAGISMO_CORTES_FOLDER = os.path.join(VISAGISMO_FOLDER, 'cortes')
VISAGISMO_FOTOS_FOLDER = os.path.join(VISAGISMO_FOLDER, 'fotos')
VISAGISMO_RESULTADOS_FOLDER = os.path.join(VISAGISMO_FOLDER, 'resultados')
MAX_VISAGISMO_IMAGE_BYTES = 10 * 1024 * 1024


# ==========================================================
# PAGAMENTO ARKHÉ (PIX)
# ==========================================================
# Credenciais da integração PJ ficam só no servidor (.env).

ARKHE_CLIENT_ID = _limpar_env('ARKHE_CLIENT_ID')

ARKHE_CLIENT_SECRET = _limpar_env('ARKHE_CLIENT_SECRET')

ARKHE_BASE_URL = (_limpar_env('ARKHE_BASE_URL') or 'https://arkhe-backend.zbbquj.easypanel.host').rstrip('/')


# ==========================================================
# PASTAS FINANCEIRO / ARKHÉ
# ==========================================================

FINANCEIRO_FOLDER = os.path.join(UPLOAD_FOLDER, 'financeiro')
COMPROVANTES_FOLDER = os.path.join(FINANCEIRO_FOLDER, 'comprovantes')

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://127.0.0.1:5173')
WAITLIST_WORKER = os.getenv('WAITLIST_WORKER', 'true').lower() in ('1','true','sim','yes')

PUBLIC_FRONTEND_URL = os.getenv('PUBLIC_FRONTEND_URL', FRONTEND_URL)

# Marketplace shipping credentials remain exclusively in the server environment.
MELHOR_ENVIO_TOKEN = _limpar_env('MELHOR_ENVIO_TOKEN')
MELHOR_ENVIO_SANDBOX = os.getenv('MELHOR_ENVIO_SANDBOX', 'false').lower() in ('1','true','yes')
MELHOR_ENVIO_USER_AGENT = os.getenv('MELHOR_ENVIO_USER_AGENT', 'Cortae marketplace')

# Issuing labels spends wallet funds and needs separately authorized write scopes.
MELHOR_ENVIO_EMITIR_ETIQUETAS = os.getenv('MELHOR_ENVIO_EMITIR_ETIQUETAS', 'false').lower() in ('1','true','yes')

# Legal operator identification: do not infer these values from login credentials.
TERMOS_RESPONSAVEL_NOME = os.getenv('TERMOS_RESPONSAVEL_NOME', '')
TERMOS_RESPONSAVEL_DOCUMENTO = os.getenv('TERMOS_RESPONSAVEL_DOCUMENTO', '')
TERMOS_RESPONSAVEL_CONTATO = os.getenv('TERMOS_RESPONSAVEL_CONTATO', '')
TERMOS_RESPONSAVEL_ENDERECO = os.getenv('TERMOS_RESPONSAVEL_ENDERECO', '')
PLATAFORMA_TAXA_PAGADOR = os.getenv('PLATAFORMA_TAXA_PAGADOR', '')
