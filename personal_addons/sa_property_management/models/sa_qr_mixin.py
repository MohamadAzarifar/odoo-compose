# -*- coding: utf-8 -*-
import base64
import uuid

from odoo import api, fields, models, _


class SaQrMixin(models.AbstractModel):
    """Reusable mixin that gives a record a stable, unguessable QR token,
    a rendered QR image, and a public status payload for the verify page."""
    _name = 'sa.qr.mixin'
    _description = 'SA QR Identification Mixin'

    sa_qr_token = fields.Char(
        string='QR Token', copy=False, index=True, readonly=True,
        help="Unguessable token encoded in the document QR code.")
    sa_qr_image = fields.Binary(
        string='QR Code', compute='_compute_sa_qr_image')

    # Human label for the kind of document; override per model.
    _sa_doc_type = _('Document')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('sa_qr_token'):
                vals['sa_qr_token'] = uuid.uuid4().hex
        return super().create(vals_list)

    def _sa_ensure_token(self):
        for rec in self:
            if not rec.sa_qr_token:
                rec.sudo().write({'sa_qr_token': uuid.uuid4().hex})
        return self

    def _sa_verify_url(self):
        self.ensure_one()
        self._sa_ensure_token()
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url') or ''
        return '%s/sa/verify/%s' % (base.rstrip('/'), self.sa_qr_token)

    def _compute_sa_qr_image(self):
        for rec in self:
            if not rec.id:
                rec.sa_qr_image = False
                continue
            try:
                url = rec._sa_verify_url()
                png = rec.env['ir.actions.report'].barcode(
                    'QR', url, width=220, height=220, humanreadable=0)
                rec.sa_qr_image = base64.b64encode(png)
            except Exception:
                rec.sa_qr_image = False

    # --- Public status payload (override per model) ---
    def _sa_status_info(self):
        """Return a safe dict rendered on the public verify page.

        Override in concrete models. Never expose sensitive internals here.
        """
        self.ensure_one()
        return {
            'doc_type': self._sa_doc_type,
            'reference': self.display_name,
            'status': '',
            'status_label': '',
            'valid': True,
            'rows': [],
        }
