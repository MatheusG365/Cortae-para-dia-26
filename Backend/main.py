"""WSGI application and local server entry point."""
if __name__ == '__main__':
    from firebird_runtime import main as check_firebird
    if check_firebird([]):
        raise SystemExit(1)

from application import app

# Route modules import application, avoiding a second app through main.
import view  # noqa: E402,F401
import Listar_usuario  # noqa: E402,F401
import arkhe  # noqa: E402,F401
import agenda_gestao  # noqa: E402,F401
import gestao  # noqa: E402,F401
import ranking_avaliacoes  # noqa: E402,F401
import metas_profissionais  # noqa: E402,F401
import admin_help  # noqa: E402,F401
import marketplace  # noqa: E402,F401
import marketplace_enderecos  # noqa: E402,F401
import termos  # noqa: E402,F401
import taxa_plataforma  # noqa: E402,F401
import midia  # noqa: E402,F401

if app.config.get('WAITLIST_WORKER', True):
    from agenda_equipe import iniciar_worker_emails
    iniciar_worker_emails()

if __name__ == '__main__':
    app.run(host=app.config['API_HOST'], port=app.config['PORT'],
            debug=app.config['DEBUG'], use_reloader=False)

