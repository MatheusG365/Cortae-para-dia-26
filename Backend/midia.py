"""Public site/app artwork, resolved only through registered image metadata.

The public allowlist is deliberately separate from the private visagismo areas.
Drive file identifiers and credentials never appear in client URLs or responses.
"""
from flask import abort
from application import app
from image_storage import serve_image


@app.get('/midia/site/<nome>', defaults={'area': 'site'})
@app.get('/midia/mobile/<nome>', defaults={'area': 'mobile'})
def midia_publica(area, nome):
    """Entrega logos, banners e fotos fixas do site/mobile em WebP pelo Drive."""
    if area not in {'site', 'mobile'}:
        abort(404)
    return serve_image(area, nome)
