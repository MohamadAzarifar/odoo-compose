# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaPropertyDealer(models.Model):
    """Real-estate dealer/agent who brings booking customers."""
    _name = 'sa.property.dealer'
    _description = 'Property Dealer / Agent'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(related='partner_id.name', store=True, readonly=True)
    partner_id = fields.Many2one(
        'res.partner', required=True, ondelete='restrict', tracking=True)
    code = fields.Char(required=True, copy=False, tracking=True,
                       default=lambda self: _('New'))
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)

    phone = fields.Char(related='partner_id.phone', readonly=False, store=True)
    email = fields.Char(related='partner_id.email', readonly=False, store=True)
    cnic = fields.Char(related='partner_id.sa_cnic', readonly=False, store=True)
    ntn = fields.Char(related='partner_id.sa_ntn', readonly=False, store=True)

    commission_percent = fields.Float(
        string='Commission (%)', digits=(6, 2), tracking=True,
        default=lambda self: float(
            self.env['ir.config_parameter'].sudo().get_param(
                'sa_property_management.default_dealer_commission') or 2.0))

    project_ids = fields.Many2many(
        'sa.property.project', string='Assigned Projects')
    booking_ids = fields.One2many(
        'sa.property.booking', 'dealer_id', string='Bookings')

    booking_count = fields.Integer(compute='_compute_stats', store=False)
    total_sales = fields.Monetary(
        currency_field='currency_id', compute='_compute_stats', store=False)
    total_commission = fields.Monetary(
        currency_field='currency_id', compute='_compute_stats', store=False)

    note = fields.Text()

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'Dealer code must be unique per company.'),
        ('partner_company_uniq', 'unique(partner_id, company_id)',
         'A contact can only have one dealer record per company.'),
        ('commission_range', 'CHECK(commission_percent >= 0 AND commission_percent <= 100)',
         'Commission must be between 0 and 100%.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', _('New')) == _('New'):
                vals['code'] = self.env['ir.sequence'].next_by_code(
                    'sa.property.dealer') or _('New')
            # Tag partner as dealer and ensure it can be paid as a vendor
            if vals.get('partner_id'):
                partner = self.env['res.partner'].browse(vals['partner_id'])
                partner.sa_is_property_dealer = True
                if partner.supplier_rank < 1:
                    partner.supplier_rank = 1
        return super().create(vals_list)

    @api.depends('booking_ids', 'booking_ids.state',
                 'booking_ids.total_price', 'commission_percent')
    def _compute_stats(self):
        for rec in self:
            confirmed = rec.booking_ids.filtered(
                lambda b: b.state in ('confirmed', 'in_payment', 'completed'))
            rec.booking_count = len(confirmed)
            rec.total_sales = sum(confirmed.mapped('total_price'))
            rec.total_commission = rec.total_sales * (rec.commission_percent or 0.0) / 100.0

    @api.constrains('partner_id')
    def _check_partner_is_company_or_individual(self):
        # Any partner is acceptable; just ensure it is set
        for rec in self:
            if not rec.partner_id:
                raise ValidationError(_("Dealer must be linked to a contact."))

    def action_view_bookings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bookings - %s', self.name),
            'res_model': 'sa.property.booking',
            'view_mode': 'list,form',
            'domain': [('dealer_id', '=', self.id)],
            'context': {'default_dealer_id': self.id},
        }
