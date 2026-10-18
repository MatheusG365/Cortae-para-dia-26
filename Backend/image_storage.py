"""Bounded WebP images, transactional references and private provider delivery.

The business transaction owns its cursor. Call batch.commit() only AFTER its
database commit; call batch.abort() after rollback. No distributed transaction
exists: an interrupted network upload can leave a private orphan for cleanup.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import io
import os
from pathlib import Path
import re
import uuid
import warnings

from flask import current_app, send_file, abort
from PIL import Image, ImageOps, UnidentifiedImageError

from application import app, conectar_banco, erro_json
from google_drive_storage import GoogleDriveStorage, DriveError

AREAS = {'perfil', 'barbearia', 'visagismo/cortes', 'visagismo/fotos',
         'visagismo/resultados', 'marketplace', 'site', 'mobile'}
MAX_INPUT = 10 * 1024 * 1024
MAX_OUTPUT = 5 * 1024 * 1024
MAX_PIXELS = 24_000_000
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$')
MANAGED_NAME = re.compile(r'^[a-f0-9]{32}\.webp$')
COLUMNS = 'NOME,AREA,PROVIDER,FILE_ID,OWNER_ID,SLOT,MIME,LARGURA,ALTURA,TAMANHO,SHA256,ATIVO'


class ImageStorageError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message); self.status = status


@app.errorhandler(ImageStorageError)
def erro_armazenamento_imagem(error):
    """Register once with this cached route dependency, not the replayed entrypoint."""
    return erro_json(str(error), error.status)


@dataclass
class StoredImage:
    filename: str
    area: str
    provider: str
    file_id: str
    owner_id: int | None
    slot: str | None
    mime: str
    width: int
    height: int
    size: int
    sha256: str
    active: int = 1
    content: bytes | None = field(default=None, repr=False)

    @property
    def url(self):
        if self.area in {'site', 'mobile'}:
            return f'/midia/{self.area}/{self.filename}'
        return f'/uploads/{self.area}/{self.filename}'


def _validate(area, filename=None):
    if area not in AREAS:
        raise ImageStorageError('Área de imagem inválida.', 400)
    if filename is not None and (not isinstance(filename, str) or not NAME.fullmatch(filename)
                                 or '..' in filename):
        raise FileNotFoundError('Imagem não encontrada.')


def compress_image(upload, max_dimension=1600):
    """Decode real image data; reject animation, bombs and unsupported formats."""
    if isinstance(upload, (bytes, bytearray)):
        raw = bytes(upload)
    elif upload is not None and hasattr(upload, 'read'):
        raw = upload.read(MAX_INPUT + 1)
    else:
        raise ImageStorageError('Selecione uma imagem válida.', 400)
    if len(raw) > MAX_INPUT:
        raise ImageStorageError('A imagem deve ter no máximo 10 MB.', 413)
    if not raw:
        raise ImageStorageError('A imagem está vazia.', 400)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as check:
                if check.format not in {'JPEG', 'PNG', 'WEBP', 'GIF'}:
                    raise ImageStorageError('Use uma imagem JPEG, PNG, WebP ou GIF estático.', 400)
                if check.width * check.height > MAX_PIXELS:
                    raise ImageStorageError('A resolução da imagem excede 24 megapixels.', 413)
                if getattr(check, 'n_frames', 1) != 1:
                    raise ImageStorageError('Envie uma imagem estática, sem animação.', 400)
                check.verify()
            with Image.open(io.BytesIO(raw)) as source:
                source.load()
                picture = ImageOps.exif_transpose(source)
                alpha = picture.mode in ('RGBA', 'LA') or 'transparency' in picture.info
                picture = picture.convert('RGBA' if alpha else 'RGB')
                bound = max(64, min(int(max_dimension or 1600), 2000))
                picture.thumbnail((bound, bound), Image.Resampling.LANCZOS)
                # Build a fresh image so EXIF, ICC, comments and GPS cannot propagate.
                clean = Image.frombytes(picture.mode, picture.size, picture.tobytes())
                encoded = io.BytesIO()
                clean.save(encoded, format='WEBP', quality=82, method=4)
                content = encoded.getvalue()
                # Flat logos, screenshots and patterned PNGs often compress much
                # better losslessly than photographic WebP. Choose actual bytes,
                # never assume the lossy encoder is the lighter representation.
                lossless = io.BytesIO()
                clean.save(lossless, format='WEBP', lossless=True, quality=82, method=4)
                if lossless.tell() < len(content):
                    content = lossless.getvalue()
                if len(content) > MAX_OUTPUT:
                    raise ImageStorageError('Não foi possível reduzir a imagem ao limite permitido.', 413)
                return content, clean.width, clean.height
    except ImageStorageError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ImageStorageError('A resolução da imagem excede o limite permitido.', 413) from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ImageStorageError('Arquivo de imagem inválido ou corrompido.', 400) from None


class _LocalStorage:
    """Explicit development provider. Never selected as a Drive failure fallback."""
    name = 'local'

    def __init__(self, config):
        self.root = Path(config.get('IMAGE_LOCAL_FOLDER') or Path(config['UPLOAD_FOLDER']) / '.managed').resolve()

    def _path(self, area, filename):
        _validate(area, filename)
        path = self.root.joinpath(*area.split('/'), filename)
        if not path.resolve().is_relative_to(self.root) or path.is_symlink():
            raise ImageStorageError('Caminho de imagem inválido.', 400)
        return path

    def put(self, area, filename, content):
        path = self._path(area, filename); path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(content)
        return area + '/' + filename

    def get(self, identifier, max_bytes):
        area, _, filename = identifier.rpartition('/')
        path = self._path(area, filename)
        with path.open('rb') as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ImageStorageError('Imagem excede o limite permitido.')
        return raw

    def delete(self, identifier):
        area, _, filename = identifier.rpartition('/')
        self._path(area, filename).unlink(missing_ok=True)

    trash = delete


def _provider(name=None):
    name = name or current_app.config.get('IMAGE_STORAGE_PROVIDER', 'google_drive')
    try:
        if name == 'google_drive':
            return GoogleDriveStorage(current_app.config)
        if name == 'local':
            return _LocalStorage(current_app.config)
        raise ImageStorageError('Provedor de imagens não configurado.')
    except DriveError as error:
        raise ImageStorageError(str(error)) from None


@contextmanager
def _cursor(cursor=None):
    if cursor is not None:
        yield cursor; return
    con = conectar_banco(); cur = con.cursor()
    try:
        yield cur
    finally:
        cur.close(); con.close()


def _table_exists(cur, name):
    cur.execute('SELECT 1 FROM RDB$RELATIONS WHERE TRIM(RDB$RELATION_NAME)=?', (name,))
    return cur.fetchone() is not None


def _lookup(cur, area, filename):
    if not _table_exists(cur, 'IMAGE_ASSET'):
        return None
    cur.execute(f'SELECT {COLUMNS} FROM IMAGE_ASSET WHERE AREA=? AND NOME=?', (area, filename))
    row = cur.fetchone()
    return StoredImage(*row) if row else None


def find_image(area, filename, cursor=None):
    """Lookup an active registered asset, without contacting its provider."""
    _validate(area, filename)
    with _cursor(cursor) as cur:
        asset = _lookup(cur, area, filename)
    return asset if asset and asset.active else None


def slot_state(area, owner_id, slot, cursor=None):
    """Return (has been managed, current asset); a deleted slot remains managed."""
    _validate(area)
    with _cursor(cursor) as cur:
        if not _table_exists(cur, 'IMAGE_SLOT'):
            return False, None
        cur.execute('SELECT NOME FROM IMAGE_SLOT WHERE AREA=? AND OWNER_ID=? AND SLOT=?',
                    (area, owner_id, slot))
        row = cur.fetchone()
        if row is None:
            return False, None
        asset = _lookup(cur, area, row[0]) if row[0] else None
        return True, asset if asset and asset.active else None


def latest_image(area, owner_id, slot=None, cursor=None):
    _validate(area)
    if slot is not None:
        return slot_state(area, owner_id, slot, cursor)[1]
    with _cursor(cursor) as cur:
        if not _table_exists(cur, 'IMAGE_ASSET'):
            return None
        cur.execute(f'SELECT FIRST 1 {COLUMNS} FROM IMAGE_ASSET WHERE AREA=? AND OWNER_ID=? '
                    'AND ATIVO=1 ORDER BY CRIADO_EM DESC,NOME DESC', (area, owner_id))
        row = cur.fetchone()
        return StoredImage(*row) if row else None


class ImageBatch:
    def __init__(self, cursor=None):
        self.connection = conectar_banco() if cursor is None else None
        self.cursor = self.connection.cursor() if self.connection else cursor
        self.new = []; self.old = []; self.closed = False

    def save(self, upload, area, owner_id=None, slot=None, max_dimension=None, *, legacy_filename=None):
        _validate(area)
        if self.closed:
            raise ImageStorageError('Operação de imagem já encerrada.')
        if slot is not None and (owner_id is None or not isinstance(slot, str) or not 1 <= len(slot) <= 80):
            raise ImageStorageError('Identificação da imagem inválida.', 400)
        content, width, height = compress_image(upload, max_dimension or (512 if area == 'perfil' else 1600))
        provider = _provider(); filename = uuid.uuid4().hex + '.webp'
        if legacy_filename is not None:
            # Offline migration only: preserve existing business references/URLs.
            # Provider objects still use an opaque UUID and actual WebP extension.
            _validate(area, legacy_filename)
        try:
            identifier = provider.put(area, filename, content)
        except DriveError as error:
            raise ImageStorageError(str(error)) from None
        asset = StoredImage(legacy_filename or filename, area, provider.name, identifier, owner_id, slot, 'image/webp',
                            width, height, len(content), hashlib.sha256(content).hexdigest(), content=content)
        self.new.append((provider, asset))
        try:
            if not _table_exists(self.cursor, 'IMAGE_ASSET') or not _table_exists(self.cursor, 'IMAGE_SLOT'):
                raise ImageStorageError('O banco precisa da migração de armazenamento de imagens.')
            if slot is not None:
                self.delete(area, owner_id, slot)
            self.cursor.execute('INSERT INTO IMAGE_ASSET (' + COLUMNS + ') VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                                (asset.filename, area, asset.provider, asset.file_id, owner_id, slot,
                                 asset.mime, width, height, asset.size, asset.sha256, 1))
            if slot is not None:
                self.cursor.execute('UPDATE OR INSERT INTO IMAGE_SLOT (AREA,OWNER_ID,SLOT,NOME) VALUES (?,?,?,?) '
                                    'MATCHING (AREA,OWNER_ID,SLOT)', (area, owner_id, slot, asset.filename))
            return asset
        except Exception:
            # Caller still rolls back its business transaction. The uploaded file can
            # safely be deleted because no committed business row references it yet.
            try:
                provider.delete(identifier)
                self.new.remove((provider, asset))
            except Exception:
                current_app.logger.warning('Imagem pendente de limpeza após falha de gravação.')
            raise

    def delete(self, area, owner_id, slot):
        _validate(area)
        if self.closed:
            raise ImageStorageError('Operação de imagem já encerrada.')
        managed, previous = slot_state(area, owner_id, slot, self.cursor)
        if previous:
            self.cursor.execute('UPDATE IMAGE_ASSET SET ATIVO=0 WHERE AREA=? AND NOME=?', (area, previous.filename))
            self.old.append(previous)
        self.cursor.execute('UPDATE OR INSERT INTO IMAGE_SLOT (AREA,OWNER_ID,SLOT,NOME) VALUES (?,?,?,NULL) '
                            'MATCHING (AREA,OWNER_ID,SLOT)', (area, owner_id, slot))
        return managed and previous is not None

    def commit(self):
        if self.closed:
            return
        if self.connection:
            try:
                self.connection.commit()
            except Exception:
                self.abort(); raise
        self.closed = True
        # Old metadata remains for audit/revocation. Private media deletion is best effort.
        for asset in self.old:
            try:
                _provider(asset.provider).trash(asset.file_id)
            except Exception:
                current_app.logger.warning('Imagem substituída pendente de limpeza no armazenamento.')
        self._close()

    def abort(self):
        if self.closed:
            return
        if self.connection:
            self.connection.rollback()
        for provider, asset in self.new:
            try:
                provider.delete(asset.file_id)
            except Exception:
                current_app.logger.warning('Upload não confirmado pendente de limpeza no armazenamento.')
        self.closed = True; self._close()

    def _close(self):
        if self.connection:
            self.cursor.close(); self.connection.close()


def read_image(area, filename, legacy_folder=None, cursor=None):
    _validate(area, filename)
    with _cursor(cursor) as cur:
        asset = _lookup(cur, area, filename)
    if asset:
        if not asset.active:
            raise FileNotFoundError('Imagem removida.')
        try:
            content = _provider(asset.provider).get(asset.file_id, min(MAX_OUTPUT, asset.size))
        except DriveError as error:
            raise ImageStorageError(str(error)) from None
        if len(content) != asset.size or hashlib.sha256(content).hexdigest() != asset.sha256:
            raise ImageStorageError('Não foi possível validar a integridade da imagem armazenada.')
        if not (content.startswith(b'RIFF') and content[8:12] == b'WEBP'):
            raise ImageStorageError('Formato da imagem armazenada inválido.')
        return content
    # UUID files are always managed: never let missing metadata bypass revocation.
    if (current_app.config.get('IMAGE_STORAGE_PROVIDER', 'google_drive') != 'local'
            or MANAGED_NAME.fullmatch(filename) or legacy_folder is None):
        raise FileNotFoundError('Imagem não encontrada.')
    root = Path(legacy_folder).resolve(); path = root / filename
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise FileNotFoundError('Imagem não encontrada.')
    with path.open('rb') as stream:
        content = stream.read(MAX_INPUT + 1)
    if len(content) > MAX_INPUT:
        raise ImageStorageError('Imagem legada excede o limite permitido.', 413)
    return content


def serve_image(area, filename, legacy_folder=None, cursor=None):
    try:
        content = read_image(area, filename, legacy_folder, cursor)
    except FileNotFoundError:
        abort(404)
    except ImageStorageError as error:
        from application import erro_json
        response, status = erro_json(str(error), error.status)
        response.headers['Cache-Control'] = 'no-store'
        return response, status
    # The route retains responsibility for its existing authentication/visibility.
    is_webp = content.startswith(b'RIFF') and content[8:12] == b'WEBP'
    response = send_file(io.BytesIO(content), mimetype='image/webp' if is_webp else None,
                         download_name=filename, conditional=False)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'private, no-cache'
    return response
