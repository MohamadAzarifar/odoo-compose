# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaBiometricVerification(models.Model):
    """Customer identity verification captured at booking or transfer time.

    The capture is intentionally device-agnostic: images are stored through
    standard Odoo image fields, so an operator can use any source supported by
    the browser — a phone camera (the upload control opens the camera on
    mobile), a webcam snapshot, or an image/template exported by any desktop
    fingerprint-scanner software. Captured images are compressed automatically
    via the shared image-optimization mixin to save server storage.
    """
    _name = 'sa.biometric.verification'
    _description = 'Biometric Customer Verification'
    _inherit = ['mail.thread', 'sa.image.optimize.mixin']
    _order = 'create_date desc, id desc'
    _rec_name = 'name'

    _sa_image_fields = ('fingerprint_image', 'face_photo', 'id_document_image')

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    customer_id = fields.Many2one(
        'res.partner', string='Customer', required=True, index=True,
        tracking=True)
    booking_id = fields.Many2one(
        'sa.property.booking', string='Booking', ondelete='cascade',
        index=True)
    transfer_id = fields.Many2one(
        'sa.property.transfer', string='Transfer', ondelete='cascade',
        index=True)

    method = fields.Selection(
        [('fingerprint', 'Fingerprint'),
         ('face', 'Face / Photo'),
         ('document', 'ID Document'),
         ('other', 'Other')],
        string='Method', default='fingerprint', required=True, tracking=True)
    device_info = fields.Char(
        string='Capture Device',
        help="Optional note on the device used to capture the biometric "
             "(e.g. phone camera, ZKTeco/Suprema/Mantra scanner, webcam).")

    fingerprint_image = fields.Image(
        string='Fingerprint', max_width=1024, max_height=1024,
        help="Fingerprint scan. On a phone the upload opens the camera; on a "
             "desktop, upload the image exported by your scanner software.")
    face_photo = fields.Image(
        string='Face Photo', max_width=1024, max_height=1024,
        help="Live photo of the customer for identity verification.")
    id_document_image = fields.Image(
        string='ID Document', max_width=1920, max_height=1920,
        help="Photo or scan of the customer's identity document.")

    state = fields.Selection(
        [('pending', 'Pending'),
         ('verified', 'Verified'),
         ('rejected', 'Rejected')],
        string='Status', default='pending', required=True, tracking=True)
    verified_by = fields.Many2one(
        'res.users', string='Verified By', readonly=True, copy=False)
    verified_on = fields.Datetime(
        string='Verified On', readonly=True, copy=False)
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.biometric.verification') or _('New')
        return super().create(vals_list)

    def action_verify(self):
        for rec in self:
            if not (rec.fingerprint_image or rec.face_photo
                    or rec.id_document_image):
                raise UserError(_(
                    "Capture at least one biometric (fingerprint, face photo "
                    "or ID document) before marking the verification as "
                    "verified."))
            rec.write({
                'state': 'verified',
                'verified_by': self.env.user.id,
                'verified_on': fields.Datetime.now(),
            })
        return True

    def action_reject(self):
        self.write({
            'state': 'rejected',
            'verified_by': self.env.user.id,
            'verified_on': fields.Datetime.now(),
        })
        return True

    def action_reset(self):
        self.write({
            'state': 'pending',
            'verified_by': False,
            'verified_on': False,
        })
        return True

    @api.model
    def get_secugen_config(self):
        """Settings the in-browser SecuGen WebAPI capture widget needs.

        Returned to the OWL fingerprint widget so it can reach the SecuGen
        WebAPI (SGIBioSrv) service running on the operator's PC. This is an
        access-controlled accessor so the widget never reads arbitrary system
        parameters directly.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'url': ICP.get_param(
                'sa_property_management.secugen_webapi_url',
                'https://localhost:8443/SGIFPCapture'),
            'license': ICP.get_param(
                'sa_property_management.secugen_license', '') or '',
            'quality': int(ICP.get_param(
                'sa_property_management.secugen_min_quality', 50) or 50),
            'timeout': int(ICP.get_param(
                'sa_property_management.secugen_timeout', 10000) or 10000),
        }
