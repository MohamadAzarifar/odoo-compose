# -*- coding: utf-8 -*-
import base64
import binascii
import io
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

try:
    from PIL import Image
except ImportError:  # pragma: no cover - Pillow ships with Odoo
    Image = None

# Quality used when re-encoding photos to JPEG. 80 keeps photos visually clean
# while cutting file size dramatically versus the PNG/JPEG most users upload.
SA_IMAGE_QUALITY = 80

# Images wider/taller than this are downscaled before storing. Property photos
# never need more than full-HD on screen, so this alone removes most of the
# wasted bytes from modern phone uploads (often 4000px+).
SA_IMAGE_MAX_DIMENSION = 1920


class SaImageOptimizeMixin(models.AbstractModel):
    """Reusable mixin that transparently re-encodes uploaded image fields to a
    compact format on create/write to save server storage.

    A model opts in by inheriting this mixin and listing the image field names
    to optimise in ``_sa_image_fields``. Opaque images are stored as JPEG
    (smallest for photos); images with transparency stay PNG (lossless) so we
    never destroy an alpha channel. The original bytes are always kept if the
    optimised result would somehow be larger, so storage never grows.
    """
    _name = 'sa.image.optimize.mixin'
    _description = 'Image Optimization Mixin'

    # Image field names to optimise. Override in the inheriting model.
    _sa_image_fields = ()

    def _sa_optimize_image_vals(self, vals):
        """Return a copy of ``vals`` with any image fields re-encoded compactly."""
        if not self._sa_image_fields or Image is None:
            return vals
        optimized = None
        for field_name in self._sa_image_fields:
            value = vals.get(field_name)
            if not value:
                continue
            new_value = self._sa_compress_image(value)
            if new_value and new_value != value:
                if optimized is None:
                    optimized = dict(vals)
                optimized[field_name] = new_value
        return optimized if optimized is not None else vals

    @staticmethod
    def _sa_compress_image(b64_value):
        """Re-encode a base64 image to a compact format and return it base64.

        Returns the original value unchanged on any failure, when the image is
        an SVG/unsupported payload, or when re-encoding would not save space, so
        an unusual upload can never block the save or inflate storage.
        """
        try:
            source = base64.b64decode(b64_value)
        except (binascii.Error, ValueError, TypeError):
            return b64_value

        # Leave SVG and empty payloads alone.
        if not source or source[:1] == b'<':
            return b64_value

        try:
            image = Image.open(io.BytesIO(source))
            image.load()
        except Exception:  # pragma: no cover - defensive
            return b64_value

        try:
            # Downscale oversized uploads while preserving aspect ratio.
            if max(image.size) > SA_IMAGE_MAX_DIMENSION:
                image.thumbnail(
                    (SA_IMAGE_MAX_DIMENSION, SA_IMAGE_MAX_DIMENSION),
                    Image.LANCZOS,
                )

            has_alpha = image.mode in ('RGBA', 'LA') or (
                image.mode == 'P' and 'transparency' in image.info
            )

            buffer = io.BytesIO()
            if has_alpha:
                # Keep transparency: store as optimised PNG.
                image.save(buffer, format='PNG', optimize=True)
            else:
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image.save(
                    buffer, format='JPEG',
                    quality=SA_IMAGE_QUALITY, optimize=True, progressive=True,
                )
            optimized = buffer.getvalue()
        except Exception:  # pragma: no cover - defensive, keep upload working
            _logger.warning(
                "Could not optimize uploaded image; storing original.",
                exc_info=True)
            return b64_value

        # Never inflate storage: keep the original if it was already smaller.
        if len(optimized) >= len(source):
            return b64_value
        return base64.b64encode(optimized)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._sa_optimize_image_vals(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        return super().write(self._sa_optimize_image_vals(vals))
