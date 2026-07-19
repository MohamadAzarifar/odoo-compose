# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

CONTRACT_STATES = [
    ('draft', 'Draft'),
    ('confirmed', 'Confirmed'),
    ('in_progress', 'In Progress'),
    ('closed', 'Closed'),
    ('cancelled', 'Cancelled'),
]


class SaConstructionContract(models.Model):
    _name = 'sa.construction.contract'
    _description = 'Construction Subcontract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Subcontract', required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'), tracking=True)
    title = fields.Char(string='Scope', required=True, tracking=True)
    construction_id = fields.Many2one(
        'sa.construction.project', string='Construction Project',
        required=True, ondelete='cascade', index=True, tracking=True)
    contractor_id = fields.Many2one(
        'res.partner', string='Subcontractor', required=True, tracking=True)
    company_id = fields.Many2one(
        related='construction_id.company_id', store=True)
    currency_id = fields.Many2one(
        related='construction_id.currency_id', store=True)

    date_signed = fields.Date(string='Date Signed', default=fields.Date.context_today)
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')
    retention_percent = fields.Float(
        string='Retention %', default=10.0, tracking=True,
        help="Percentage withheld on each certificate until final handover.")
    notes = fields.Html(string='Terms')

    state = fields.Selection(
        CONTRACT_STATES, default='draft', required=True, tracking=True)

    boq_line_ids = fields.One2many(
        'sa.construction.boq.line', 'contract_id', string='Bill of Quantities')
    ipc_ids = fields.One2many(
        'sa.construction.ipc', 'contract_id', string='Payment Certificates')

    contract_value = fields.Monetary(
        string='Contract Value', compute='_compute_contract_value', store=True)
    amount_certified = fields.Monetary(
        string='Certified', compute='_compute_certified',
        help="Gross value certified through interim payment certificates.")
    amount_billed = fields.Monetary(
        string='Billed', compute='_compute_certified',
        help="Net value invoiced by the subcontractor.")
    amount_retained = fields.Monetary(
        string='Retained', compute='_compute_certified',
        help="Retention money withheld so far.")
    amount_remaining = fields.Monetary(
        string='Remaining', compute='_compute_certified')
    progress = fields.Float(
        string='Certified %', compute='_compute_certified')

    ipc_count = fields.Integer(compute='_compute_counts')

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)',
         'The subcontract reference must be unique per company.'),
        ('retention_range', 'CHECK(retention_percent >= 0 AND retention_percent <= 100)',
         'Retention percentage must be between 0 and 100.'),
    ]

    @api.depends('boq_line_ids.amount')
    def _compute_contract_value(self):
        for rec in self:
            rec.contract_value = sum(rec.boq_line_ids.mapped('amount'))

    @api.depends('ipc_ids.state', 'ipc_ids.amount_gross',
                 'ipc_ids.amount_net', 'ipc_ids.retention_amount',
                 'contract_value')
    def _compute_certified(self):
        for rec in self:
            certified = rec.ipc_ids.filtered(
                lambda i: i.state in ('approved', 'billed'))
            rec.amount_certified = sum(certified.mapped('amount_gross'))
            rec.amount_billed = sum(
                rec.ipc_ids.filtered(lambda i: i.state == 'billed')
                .mapped('amount_gross'))
            rec.amount_retained = sum(certified.mapped('retention_amount'))
            rec.amount_remaining = rec.contract_value - rec.amount_certified
            rec.progress = (
                (rec.amount_certified / rec.contract_value) * 100.0
                if rec.contract_value else 0.0)

    def _compute_counts(self):
        for rec in self:
            rec.ipc_count = len(rec.ipc_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.construction.contract') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if not rec.boq_line_ids:
                raise UserError(_(
                    "Add at least one Bill of Quantities line before "
                    "confirming the subcontract."))
            rec.state = 'confirmed'

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_close(self):
        for rec in self:
            open_ipcs = rec.ipc_ids.filtered(lambda i: i.state == 'draft')
            if open_ipcs:
                raise UserError(_(
                    "Approve or delete draft payment certificates before "
                    "closing the subcontract."))
            rec.state = 'closed'

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_create_ipc(self):
        self.ensure_one()
        if self.state not in ('confirmed', 'in_progress'):
            raise UserError(_(
                "Confirm the subcontract before certifying work."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Payment Certificate'),
            'res_model': 'sa.construction.ipc',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_contract_id': self.id,
                'default_construction_id': self.construction_id.id,
            },
        }

    def action_view_ipcs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payment Certificates'),
            'res_model': 'sa.construction.ipc',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {
                'default_contract_id': self.id,
                'default_construction_id': self.construction_id.id,
            },
        }


class SaConstructionBoqLine(models.Model):
    _name = 'sa.construction.boq.line'
    _description = 'Bill of Quantities Line'
    _order = 'contract_id, sequence, id'

    contract_id = fields.Many2one(
        'sa.construction.contract', string='Subcontract',
        required=True, ondelete='cascade', index=True)
    construction_id = fields.Many2one(
        related='contract_id.construction_id', store=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product', string='Item',
        help="Optional catalogue item linked to this work line.")
    name = fields.Char(string='Description', required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit')
    quantity = fields.Float(string='Quantity', default=1.0, digits='Product Unit of Measure')
    unit_rate = fields.Monetary(string='Rate')
    amount = fields.Monetary(string='Amount', compute='_compute_amount', store=True)
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True)

    ipc_line_ids = fields.One2many(
        'sa.construction.ipc.line', 'boq_line_id', string='Certified Lines')
    qty_certified = fields.Float(
        string='Certified Qty', compute='_compute_certified',
        digits='Product Unit of Measure')
    qty_remaining = fields.Float(
        string='Remaining Qty', compute='_compute_certified',
        digits='Product Unit of Measure')
    progress = fields.Float(string='Progress %', compute='_compute_certified')

    @api.depends('quantity', 'unit_rate')
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.unit_rate

    @api.depends('quantity', 'ipc_line_ids.quantity', 'ipc_line_ids.ipc_id.state')
    def _compute_certified(self):
        for line in self:
            certified = sum(line.ipc_line_ids.filtered(
                lambda l: l.ipc_id.state in ('approved', 'billed')
            ).mapped('quantity'))
            line.qty_certified = certified
            line.qty_remaining = line.quantity - certified
            line.progress = (
                (certified / line.quantity) * 100.0 if line.quantity else 0.0)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            if not self.name:
                self.name = self.product_id.display_name
            if not self.uom_id:
                self.uom_id = self.product_id.uom_id
            if not self.unit_rate:
                self.unit_rate = self.product_id.standard_price
