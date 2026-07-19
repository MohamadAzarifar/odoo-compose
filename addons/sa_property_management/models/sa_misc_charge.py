# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaMiscCharge(models.Model):
    """Miscellaneous charges applied during transfer or booking
    (file transfer fee, society maintenance, utility transfer, NOC, etc.)."""
    _name = 'sa.misc.charge'
    _description = 'Property Miscellaneous Charge'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    country_id = fields.Many2one(
        'res.country', string='Country',
        help="Country this charge applies to. Leave empty to apply it to every "
             "country. The transfer engine pulls charges for the operating "
             "country set in Property Management settings.")

    amount_type = fields.Selection(
        [('fixed', 'Fixed Amount'),
         ('percent', 'Percentage of Sale Price'),
         ('per_unit_area', 'Per Unit of Area')],
        default='fixed', required=True)
    amount = fields.Monetary(currency_field='currency_id')
    rate = fields.Float(string='Rate (%)', digits=(6, 4))

    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)

    payer = fields.Selection(
        [('buyer', 'Buyer'),
         ('seller', 'Seller'),
         ('shared', 'Shared (50/50)')],
        default='buyer', required=True)

    account_id = fields.Many2one(
        'account.account',
        domain="[('company_ids', 'in', company_id)]",
        help="Account credited when this charge is posted.")

    apply_on = fields.Selection(
        [('transfer', 'Property Transfer only'),
         ('booking', 'Booking only'),
         ('both', 'Both Booking & Transfer')],
        default='transfer', required=True)

    _sql_constraints = [
        ('code_company_country_uniq', 'unique(code, company_id, country_id)',
         'Charge code must be unique per country and company.'),
    ]

    @api.constrains('amount_type', 'amount', 'rate')
    def _check_amounts(self):
        for rec in self:
            if rec.amount_type in ('fixed', 'per_unit_area') and rec.amount <= 0:
                raise ValidationError(
                    _("Charge '%s' has amount_type=%s but the amount is zero.",
                      rec.name, rec.amount_type))
            if rec.amount_type == 'percent' and rec.rate <= 0:
                raise ValidationError(
                    _("Charge '%s' uses percentage but rate is zero.", rec.name))

    def compute_charge(self, sale_price, area=0.0):
        """Return the charge amount."""
        self.ensure_one()
        if self.amount_type == 'fixed':
            return self.amount
        if self.amount_type == 'percent':
            return (sale_price or 0.0) * (self.rate or 0.0) / 100.0
        if self.amount_type == 'per_unit_area':
            return (area or 0.0) * (self.amount or 0.0)
        return 0.0
