# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaDealerAllocation(models.Model):
    """Inventory allocation handing a set of properties to a dealer to sell."""
    _name = 'sa.dealer.allocation'
    _description = 'Dealer Inventory Allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'sa.qr.mixin']
    _order = 'allocation_date desc, id desc'

    _sa_doc_type = _('Dealer Allocation')

    name = fields.Char(string='Reference', required=True, copy=False,
                       default=lambda self: _('New'), tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)

    dealer_id = fields.Many2one(
        'sa.property.dealer', string='Dealer', required=True, tracking=True)
    project_id = fields.Many2one(
        'sa.property.project', string='Project', tracking=True)
    allocation_date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True)
    expiry_date = fields.Date(string='Valid Until', tracking=True)

    property_ids = fields.Many2many(
        'sa.property', string='Allocated Units')
    property_count = fields.Integer(
        compute='_compute_property_count', store=True)

    state = fields.Selection(
        [('draft', 'Draft'),
         ('allocated', 'Allocated'),
         ('returned', 'Returned'),
         ('cancelled', 'Cancelled')],
        default='draft', required=True, tracking=True, copy=False)
    note = fields.Text()

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'Allocation reference must be unique per company.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.dealer.allocation') or _('New')
        return super().create(vals_list)

    @api.depends('property_ids')
    def _compute_property_count(self):
        for rec in self:
            rec.property_count = len(rec.property_ids)

    def action_allocate(self):
        self.write({'state': 'allocated'})

    def action_return(self):
        self.write({'state': 'returned'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset(self):
        self.write({'state': 'draft'})

    def _sa_status_info(self):
        self.ensure_one()
        labels = dict(self._fields['state'].selection)
        return {
            'doc_type': self._sa_doc_type,
            'reference': self.name,
            'status': self.state,
            'status_label': labels.get(self.state, self.state),
            'valid': self.state == 'allocated',
            'rows': [
                (_('Dealer'), self.dealer_id.name or ''),
                (_('Project'), self.project_id.name or ''),
                (_('Allocation Date'), str(self.allocation_date or '')),
                (_('Valid Until'), str(self.expiry_date or '')),
                (_('Units Allocated'), str(self.property_count)),
            ],
        }
