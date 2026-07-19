# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaPropertyDocument(models.Model):
    """A legal / ownership document tracked for a property unit.

    Captures the paperwork that accompanies a unit through its lifecycle —
    allotment letters, booking forms, possession certificates, NOC/NDC
    clearances, utility connections and registry/transfer deeds — together
    with their issue/expiry dates, responsible owner and file attachments.
    """
    _name = 'sa.property.document'
    _description = 'Property Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'issue_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, index=True,
        default=lambda self: _('New'), tracking=True)
    document_type = fields.Selection(
        [('allotment_letter', 'Allotment Letter'),
         ('booking_form', 'Booking Form'),
         ('possession_certificate', 'Possession Certificate'),
         ('noc', 'No Objection Certificate (NOC)'),
         ('ndc', 'No Demand Certificate (NDC)'),
         ('utility_connection', 'Utility Connection'),
         ('registry', 'Registry / Sub-Registrar'),
         ('transfer_deed', 'Transfer Deed'),
         ('payment_clearance', 'Payment Clearance'),
         ('agreement', 'Sale Agreement'),
         ('cnic', 'CNIC / Identity'),
         ('other', 'Other')],
        string='Document Type', required=True, default='allotment_letter',
        tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'),
         ('requested', 'Requested'),
         ('in_progress', 'In Progress'),
         ('issued', 'Issued'),
         ('expired', 'Expired'),
         ('cancelled', 'Cancelled')],
        default='draft', required=True, tracking=True, copy=False)

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True,
        index=True)
    property_id = fields.Many2one(
        'sa.property', string='Property', required=True, index=True,
        ondelete='cascade', tracking=True)
    booking_id = fields.Many2one(
        'sa.property.booking', string='Booking', index=True,
        ondelete='set null', tracking=True,
        domain="[('property_id', '=', property_id)]",
        help="Optional booking this document is associated with.")
    transfer_id = fields.Many2one(
        'sa.property.transfer', string='Transfer', index=True,
        ondelete='set null', tracking=True,
        domain="[('property_id', '=', property_id)]",
        help="Optional ownership transfer this document is associated with.")
    partner_id = fields.Many2one(
        'res.partner', string='Related Party', tracking=True,
        help="Customer or owner this document concerns.")
    responsible_id = fields.Many2one(
        'res.users', string='Responsible', tracking=True,
        default=lambda self: self.env.user)

    reference = fields.Char(
        string='Document No.',
        help="External/official number printed on the document.")
    issue_date = fields.Date(string='Issue Date', tracking=True)
    expiry_date = fields.Date(string='Expiry Date', tracking=True)
    is_expired = fields.Boolean(
        string='Expired', compute='_compute_is_expired', store=False)

    attachment_ids = fields.Many2many(
        'ir.attachment', 'sa_property_document_ir_attachment_rel',
        'document_id', 'attachment_id', string='Files')
    attachment_count = fields.Integer(
        string='File Count',
        compute='_compute_attachment_count', store=False)
    note = fields.Html(string='Notes')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'Document reference must be unique per company.'),
    ]

    @api.depends('expiry_date', 'state')
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = bool(
                rec.expiry_date and rec.expiry_date < today
                and rec.state not in ('cancelled',))

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for rec in self:
            rec.attachment_count = len(rec.attachment_ids)

    @api.onchange('booking_id')
    def _onchange_booking_id(self):
        if self.booking_id:
            if not self.property_id:
                self.property_id = self.booking_id.property_id
            if not self.partner_id:
                self.partner_id = self.booking_id.customer_id

    @api.onchange('transfer_id')
    def _onchange_transfer_id(self):
        if self.transfer_id:
            if not self.property_id:
                self.property_id = self.transfer_id.property_id
            if not self.partner_id:
                self.partner_id = self.transfer_id.to_partner_id

    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            if rec.issue_date and rec.expiry_date \
                    and rec.expiry_date < rec.issue_date:
                raise ValidationError(_(
                    "Expiry date cannot be earlier than the issue date "
                    "for document '%s'."
                ) % (rec.display_name,))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.property.document') or _('New')
        return super().create(vals_list)

    def action_request(self):
        self.write({'state': 'requested'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_mark_issued(self):
        for rec in self:
            vals = {'state': 'issued'}
            if not rec.issue_date:
                vals['issue_date'] = fields.Date.context_today(rec)
            rec.write(vals)

    def action_mark_expired(self):
        self.write({'state': 'expired'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_open_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Files - %s', self.display_name),
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id,
            },
        }
