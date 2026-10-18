"""Offline, idempotent migration of referenced legacy images; originals stay intact.

Default mode only counts eligible local images. Applying requires configured
Google OAuth, an explicit database identity and a nonempty external backup.
Existing aliases remain in business rows, so bookmarks and private-photo ACLs
continue to work. --incluir-estaticas also migrates the explicit web/mobile
content manifest. Native build icons/splash remain local. No files are deleted.
"""
from dataclasses import dataclass, field
import argparse
import json
from pathlib import Path
import re
import sys

from application import app, conectar_banco
from database import travar_usuario
from image_storage import ImageBatch, ImageStorageError, NAME, slot_state
from migrations.image_storage_schema import migrar_imagens
from google_drive_storage import GoogleDriveStorage, DriveError
from migrations.schema_utils import objeto_existe, coluna_existe

EXTENSIONS = ('.jpeg', '.jpg', '.png', '.webp')
SALON_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')
REFERENCES = (
    ('visagismo/cortes', 'CORTE_VISAGISMO', 'ID_CORTE', 'IMAGEM_ROTA'),
    ('visagismo/fotos', 'VISAGISMO_SESSAO', 'ID_VISAGISMO', 'FOTO_ROTA'),
    ('visagismo/resultados', 'VISAGISMO_SESSAO', 'ID_VISAGISMO', 'RESULTADO_ROTA'),
)


@dataclass
class Reference:
    table: str
    key: str
    record_id: int
    column: str
    original: str


@dataclass
class PlanItem:
    area: str
    filename: str
    path: Path
    owners: set = field(default_factory=set)
    slot: str | None = None
    references: list = field(default_factory=list)


@dataclass
class RemotePlanItem:
    area: str
    original: str
    owners: set = field(default_factory=set)
    references: list = field(default_factory=list)


SITE_IMAGES = ('banner.png', 'cadastro.png', 'celular.png', 'elbrabo.png',
               'gordollas.png', 'homem-com-celular.png', 'imagem_login.png',
               'logobranca.png', 'logopreta.png', 'logosolo.png', 'mvcortes.png',
               'siralfred.png', 'sirAlfredpDentro.png', 'sirAlfredpDentro1.webp',
               'sirAlfredpDentro2.webp', 'sirAlfredpDentro3.png')
MOBILE_IMAGES = (('logo-cortae.png', 'logo-cortae.png'),
                 ('fundo-login.png', 'fundo-login.png'), ('Banner 1.png', 'banner-1.png'))


def static_inventory(cur, site_root, mobile_root):
    """Explicit content-only manifest; never traverses native icons or splash assets."""
    items = []; managed = 0
    for area, root, manifest in (
            ('site', site_root, [(name, name) for name in SITE_IMAGES]),
            ('mobile', mobile_root, MOBILE_IMAGES)):
        root = Path(root).resolve()
        for source, alias in manifest:
            item = PlanItem(area, alias, root / source)
            if _managed(cur, item):
                managed += 1
                continue
            path = item.path
            if (path.is_symlink() or not path.is_file()
                    or not path.resolve().is_relative_to(root)):
                raise ValueError(f'Imagem fixa não encontrada no inventário {area}: {source}')
            items.append(item)
    return items, managed


def safe_local(root, filename):
    if not isinstance(filename, str) or not NAME.fullmatch(filename) or '..' in filename:
        return None
    root = Path(root).resolve(); path = root / filename
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        return None
    return path


def reference_name(value, area):
    if not isinstance(value, str):
        return None
    prefix = '/uploads/' + area + '/'
    name = value[len(prefix):] if value.startswith(prefix) else value
    if not NAME.fullmatch(name) or '..' in name or Path(name).suffix.lower() not in EXTENSIONS:
        return None
    return name


def _managed(cur, item):
    if isinstance(item, RemotePlanItem):
        return False
    if item.slot:
        managed, _ = slot_state(item.area, next(iter(item.owners)), item.slot, cur)
        if managed:
            return True
    if objeto_existe(cur, 'tabela', 'IMAGE_ASSET'):
        cur.execute('SELECT 1 FROM IMAGE_ASSET WHERE AREA=? AND NOME=?', (item.area, item.filename))
        return cur.fetchone() is not None  # Inactive aliases must never be resurrected.
    return False


def inventory(cur, config, include_external=False):
    """Read references, selecting exactly the same legacy files as serving helpers."""
    pending = {}; skipped = {'gerenciadas': 0, 'ausentes_ou_externas': 0}
    root = Path(config['UPLOAD_FOLDER'])
    cur.execute('SELECT ID_USUARIO,TIPO FROM USUARIO')
    owners = cur.fetchall()
    for owner, kind in owners:
        sources = [('perfil', config['PERFIL_FOLDER'], str(owner), 'profile', EXTENSIONS)]
        if kind == 2:
            sources += [('barbearia', root / 'barbearia', str(owner), 'logo', SALON_EXTENSIONS)]
            sources += [('barbearia', root / 'barbearia', f'{owner}_{number}', f'gallery{number}', SALON_EXTENSIONS)
                        for number in range(1, 6)]
        for area, folder, stem, slot, extensions in sources:
            path = next((p for ext in extensions if (p := safe_local(folder, stem + ext))), None)
            if path is None:
                continue
            item = PlanItem(area, path.name, path, {int(owner)}, slot)
            if _managed(cur, item):
                skipped['gerenciadas'] += 1
            else:
                pending[(area, path.name)] = item
    for area, table, key, column in REFERENCES:
        if not objeto_existe(cur, 'tabela', table) or not coluna_existe(cur, table, column):
            continue
        cur.execute(f'SELECT {key},ID_USUARIO,{column} FROM {table} WHERE {column} IS NOT NULL')
        for record_id, owner, value in cur.fetchall():
            filename = reference_name(value, area)
            if filename and _managed(cur, PlanItem(area, filename, None)):
                skipped['gerenciadas'] += 1; continue
            if (include_external and table == 'CORTE_VISAGISMO'
                    and isinstance(value, str) and value.startswith('https://')):
                identity = (area, value)
                item = pending.get(identity) or RemotePlanItem(area, value)
                if owner is not None:
                    item.owners.add(int(owner))
                item.references.append(Reference(table, key, int(record_id), column, value))
                pending[identity] = item
                continue
            path = safe_local(root / area, filename) if filename else None
            if path is None:
                skipped['ausentes_ou_externas'] += 1; continue
            identity = (area, filename)
            item = pending.get(identity) or PlanItem(area, filename, path)
            if owner is not None:
                item.owners.add(int(owner))
            item.references.append(Reference(table, key, int(record_id), column, value))
            pending[identity] = item
    ready = []
    for item in pending.values():
        if _managed(cur, item):
            skipped['gerenciadas'] += 1
        else:
            ready.append(item)
    return ready, skipped


def validate_backup(config, database, backup):
    if not database or not backup:
        raise ValueError('Para aplicar, informe --banco e --backup do banco principal.')
    expected = Path(config['DB_NAME']).resolve()
    if Path(database).resolve() != expected:
        raise ValueError('A identidade do banco informado difere da configuração do servidor.')
    supplied = Path(backup)
    candidate = supplied.resolve()
    if candidate == expected or supplied.is_symlink() or not candidate.is_file() or candidate.stat().st_size == 0:
        raise ValueError('Informe um backup externo existente e não vazio; o banco ativo não é um backup.')
    # A file existence check cannot certify recovery. The operator must have
    # produced and verified this backup (e.g. gbak restore) before this command.
    return candidate


def _revalidate(cur, item):
    for owner in sorted(item.owners):
        travar_usuario(cur, owner)
    if _managed(cur, item):
        return False
    for reference in item.references:
        cur.execute(f'SELECT {reference.column} FROM {reference.table} WHERE {reference.key}=? WITH LOCK',
                    (reference.record_id,))
        row = cur.fetchone()
        if row is None or row[0] != reference.original:
            return False
    if isinstance(item, RemotePlanItem):
        return True
    # Detect removed/replaced local files. The path is opened without following
    # symbolic links below and bytes are bounded before Pillow sees the input.
    path = item.path
    return (not path.is_symlink() and path.is_file()
            and path.resolve().is_relative_to(path.parent.resolve()))


def migrate_item(item, connect=conectar_banco):
    raw = None
    if isinstance(item, RemotePlanItem):
        # Uses the existing bounded HTTPS downloader: public DNS validation,
        # DNS pinning and redirect revalidation. Download BEFORE opening locks.
        from visagismo import carregar_referencia_corte
        downloaded = carregar_referencia_corte(item.original)
        if not downloaded:
            raise ValueError('Não foi possível obter a referência externa.')
        raw = downloaded[0]
    con = connect(); cur = con.cursor(); batch = ImageBatch(cur)
    try:
        if not _revalidate(cur, item):
            con.rollback(); batch.abort(); return 'alterada_ou_gerenciada'
        if raw is None:
            from image_storage import MAX_INPUT
            before = item.path.stat()
            with item.path.open('rb') as stream:
                raw = stream.read(MAX_INPUT + 1)
            after = item.path.stat()
            if (before.st_mtime_ns, before.st_size, before.st_ino) != (after.st_mtime_ns, after.st_size, after.st_ino):
                raise ValueError('Imagem alterada durante a migração.')
        owner = next(iter(item.owners)) if len(item.owners) == 1 else None
        if isinstance(item, RemotePlanItem):
            asset = batch.save(raw, item.area, owner_id=owner)
            for reference in item.references:
                cur.execute(f'UPDATE {reference.table} SET {reference.column}=? WHERE {reference.key}=?',
                            (asset.filename, reference.record_id))
        else:
            batch.save(raw, item.area, owner_id=owner, slot=item.slot, legacy_filename=item.filename)
        # Aliases preserve all existing business references, including files
        # shared by several sessions. Metadata is committed in this same txn.
        con.commit(); batch.commit(); return 'migrada'
    except Exception:
        con.rollback(); batch.abort(); raise
    finally:
        cur.close(); con.close()


def run(args, config=None, connect=None):
    config = app.config if config is None else config
    connect = conectar_banco if connect is None else connect
    if args.aplicar:
        validate_backup(config, args.banco, args.backup)
        if config.get('IMAGE_STORAGE_PROVIDER', 'google_drive') != 'google_drive':
            raise ValueError('A migração só aplica quando o provedor configurado é Google Drive.')
        GoogleDriveStorage(config)  # Validate local credentials before any schema mutation.
        migrar_imagens()
    con = connect(); cur = con.cursor()
    try:
        items, skipped = inventory(cur, config, getattr(args, 'incluir_referencias_externas', False))
        if getattr(args, 'incluir_estaticas', False):
            if not getattr(args, 'raiz_site', None) or not getattr(args, 'raiz_mobile', None):
                raise ValueError('Informe --raiz-site e --raiz-mobile com --incluir-estaticas.')
            static, managed = static_inventory(cur, args.raiz_site, args.raiz_mobile)
            items.extend(static)
            skipped['gerenciadas'] += managed
    finally:
        cur.close(); con.close()
    report = {'modo': 'aplicar' if args.aplicar else 'planejar', 'planejadas': len(items),
              'por_area': {area: sum(item.area == area for item in items) for area in sorted({i.area for i in items})},
              'ignoradas': skipped, 'migradas': 0, 'alteradas_ou_gerenciadas': 0, 'erros': 0,
              'originais_preservados': True}
    if args.aplicar:
        for item in items:
            try:
                outcome = migrate_item(item, connect)
                key = 'migradas' if outcome == 'migrada' else 'alteradas_ou_gerenciadas'
                report[key] += 1
            except Exception:
                # No filenames, private paths, exception reprs, photos or secrets in reports.
                report['erros'] += 1
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--planejar', action='store_true', help='Somente inventário (padrão).')
    modes.add_argument('--aplicar', action='store_true', help='Converter e migrar referências para o Google Drive.')
    parser.add_argument('--banco', help='Caminho exato do banco principal configurado.')
    parser.add_argument('--backup', help='Backup externo previamente criado e verificado pelo operador.')
    parser.add_argument('--incluir-estaticas', action='store_true', help='Incluir fotos, banners e logos fixos do site/mobile.')
    parser.add_argument('--raiz-site', help='Pasta Frontend/public com as imagens do manifesto.')
    parser.add_argument('--raiz-mobile', help='Pasta de assets contendo as três imagens de conteúdo do mobile.')
    parser.add_argument('--incluir-referencias-externas', action='store_true',
                        help='Converter referências HTTPS do catálogo de cortes, usando download com proteção SSRF.')
    args = parser.parse_args(argv)
    try:
        with app.app_context():
            report = run(args)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report['erros'] else 0
    except (ValueError, ImageStorageError, DriveError) as error:
        print(str(error), file=sys.stderr); return 2
    except Exception:
        print('Não foi possível consultar ou migrar as imagens. Verifique a configuração do servidor.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
