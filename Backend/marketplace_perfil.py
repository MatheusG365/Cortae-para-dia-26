"""Read-only business presentation, with explicit public column whitelists."""
from pathlib import Path
from flask import current_app, has_app_context


PROFILE_FIELDS = ('id_usuario', 'cor_primaria', 'cor_secundaria', 'cor_terciaria',
                  'cor_texto_primario', 'cor_texto_secundario', 'historia',
                  'localizacao', 'contato_telefone', 'contato_email', 'instagram',
                  'num_funcionarios')


def business_images(upload_root, salon, cursor=None):
    """Read existing public business assets without creating directories."""
    folder = Path(upload_root)/'barbearia'
    def image(stem, slot):
        if cursor is not None:
            from image_storage import slot_state
            managed, stored = slot_state('barbearia', int(salon), slot, cursor=cursor)
            if managed:
                return stored.url if stored else None
        if (not has_app_context()
                or current_app.config.get('IMAGE_STORAGE_PROVIDER', 'google_drive') != 'local'):
            return None
        for extension in ('jpg', 'jpeg', 'png', 'webp'):
            filename = f'{stem}.{extension}'
            if (folder/filename).is_file():
                return '/uploads/barbearia/'+filename
        return None
    photos = []
    for number in range(1, 6):
        url = image(f'{salon}_{number}', f'gallery{number}')
        if url:
            photos.append({'numero': number, 'url': url})
    return image(salon, 'logo'), photos


def public_profile(cur, salon, upload_root):
    cur.execute('''SELECT NOME FROM USUARIO WHERE ID_USUARIO=? AND TIPO=2
        AND ATIVO=1 AND EMAIL_CONFIRMADO=1''', (salon,))
    account = cur.fetchone()
    if not account:
        return None
    result = dict(nome_barbearia=account[0], personalizado=False,
                  personalizacao=None, funcionarios=[], servicos=[],
                  dias_servico=[], logo=None, fotos=[])
    cur.execute('''SELECT ID_USUARIO,COR_PRIMARIA,COR_SECUNDARIA,COR_TERCIARIA,
        COR_TEXTO_PRIMARIO,COR_TEXTO_SECUNDARIO,TEXTO,LOCALIZACAO,
        CONTATO_TELEFONE,CONTATO_EMAIL,INSTAGRAM,NUM_FUNCIONARIOS
        FROM PERSONALIZACAO WHERE ID_USUARIO=?''', (salon,))
    row = cur.fetchone()
    if not row:
        return result
    profile = dict(zip(PROFILE_FIELDS, row))
    profile['historia'] = str(profile['historia'] or '')
    cur.execute('''SELECT ID_SERVICO,NOME_SERVICO,PRECO,DURACAO,DESCRICAO_BREVE,GENERO
        FROM SERVICO WHERE ID_USUARIO=? AND ATIVO=1 ORDER BY NOME_SERVICO''', (salon,))
    services = [dict(id_servico=r[0], nome=r[1], preco=float(r[2] or 0), duracao=r[3],
                     descricao=r[4], genero=r[5] or 'unissex', ativo=True)
                for r in cur.fetchall()]
    cur.execute('''SELECT ID_DIA,DIAS,ENTRADA_MANHA,SAIDA_MANHA,ENTRADA_TARDE,SAIDA_TARDE
        FROM DIAS_DE_SERVICO WHERE ID_USUARIO=? ORDER BY ID_DIA''', (salon,))
    days = [dict(id_dia=r[0], dia=r[1], **{k: str(v) if v else None for k, v in
            zip(('entrada_manha', 'saida_manha', 'entrada_tarde', 'saida_tarde'), r[2:])})
            for r in cur.fetchall()]
    cur.execute('''SELECT ID_FUNCIONARIO,NOME,DESCRICAO FROM FUNCIONARIO
        WHERE ID_BARBEARIA=? AND ATIVO=1 ORDER BY ID_FUNCIONARIO''', (salon,))
    workers = []
    for worker_id, name, description in cur.fetchall():
        cur.execute('''SELECT SPF.ID_SERVICO FROM SERVICO_POR_FUNCIONARIO SPF
            JOIN SERVICO S ON S.ID_SERVICO=SPF.ID_SERVICO
            WHERE SPF.ID_FUNCIONARIO=? AND S.ID_USUARIO=? AND S.ATIVO=1
            ORDER BY SPF.ID_SERVI_FUNCI''', (worker_id, salon))
        worker_services = [r[0] for r in cur.fetchall()]
        cur.execute('''SELECT FD.ID_DIA FROM FUNCIONARIO_DIA FD
            JOIN DIAS_DE_SERVICO D ON D.ID_DIA=FD.ID_DIA
            WHERE FD.ID_FUNCIONARIO=? AND D.ID_USUARIO=? ORDER BY FD.ID_DIA''', (worker_id, salon))
        workers.append(dict(id_funcionario=worker_id, nome=name, descricao=description,
                            servicos=worker_services, dias=[r[0] for r in cur.fetchall()]))
    profile['num_funcionarios'] = len(workers)
    logo, photos = business_images(upload_root, salon, cursor=cur)
    result.update(personalizado=True, personalizacao=profile, servicos=services,
                  dias_servico=days, funcionarios=workers, logo=logo, fotos=photos)
    return result
