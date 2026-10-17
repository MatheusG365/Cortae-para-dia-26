"""WSGI application and local server entry point."""
from application import app, conectar_banco
from database import inicializar_banco

if app.config.get('STARTUP_MIGRATIONS', True):
    with app.app_context():
        try:
            inicializar_banco()
            app.logger.info('Banco principal preparado.')
        except Exception:
            app.logger.exception('Falha na preparação do banco principal; consulte /health.')

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
import termos  # noqa: E402,F401
import taxa_plataforma  # noqa: E402,F401
import midia  # noqa: E402,F401

if app.config.get('STARTUP_MIGRATIONS', True):
    from agenda_schema import migrar_agenda, migrar_gestao_agenda
    from gestao_schema import migrar_gestao
    from ranking_schema import migrar_ranking_avaliacoes
    from metas_schema import migrar_metas
    from marketplace_schema import migrar_marketplace
    from termos_schema import migrar_termos_taxa
    from image_storage_schema import migrar_imagens
    with app.app_context():
        migrar_agenda()
        migrar_gestao_agenda()
        migrar_gestao()
        migrar_ranking_avaliacoes()
        migrar_metas()
        migrar_marketplace()
        migrar_termos_taxa()
        migrar_imagens()
    if app.config.get('WAITLIST_WORKER', True):
        from agenda_equipe import iniciar_worker_emails
        iniciar_worker_emails()

if __name__ == '__main__':
    app.run(host=app.config['API_HOST'], port=app.config['PORT'],
            debug=app.config['DEBUG'], use_reloader=False)

