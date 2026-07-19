# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class SaConstructionIpc(models.Model):
    _name = 'sa.construction.ipc'
    _description = 'Interim Payment Certificate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Certificate', required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'), tracking=True)
    contract_id = fields.Many2one(
        'sa.construction.contract', string='Subcontract',
        required=True, ondelete='cascade', index=True, tracking=True,
        domain="[('state', 'in', ('confirmed', 'in_progress'))]")
    construction_id = fields.Many2one(
        'sa.construction.project', string='Construction Project',
        related='contract_id.construction_id', store=True, index=True)
    contractor_id = fields.Many2one(
        'res.partner', related='contract_id.contractor_id', store=True)
    company_id = fields.Many2one(
        related='contract_id.company_id', store=True)
    currency_id = fields.Many2one(
        related='contract_id.currency_id', store=True)

    date = fields.Date(
        string='Certificate Date', default=fields.Date.context_today,
        required=True, tracking=True)
    retention_percent = fields.Float(
        string='Retention %', tracking=True,
        help="Defaults to the subcontract retention rate.")
    notes = fields.Html(string='Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('billed', 'Billed'),
    ], default='draft', required=True, tracking=True)

    line_ids = fields.One2many(
        'sa.construction.ipc.line', 'ipc_id', string='Certified Work')

    amount_gross = fields.Monetary(
        string='Gross', compute='_compute_amounts', store=True)
    retention_amount = fields.Monetary(
        string='Retention', compute='_compute_amounts', store=True)
    amount_net = fields.Monetary(
        string='Net Payable', compute='_compute_amounts', store=True,
        help="Amount payable now after withholding retention.")

    bill_id = fields.Many2one(
        'account.move', string='Vendor Bill', readonly=True, copy=False)
    bill_state = fields.Selection(
        related='bill_id.state', string='Bill Status')

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)',
         'The certificate reference must be unique per company.'),
    ]

    @api.depends('line_ids.amount', 'retention_percent')
    def _compute_amounts(self):
        for rec in self:
            gross = sum(rec.line_ids.mapped('amount'))
            retention = gross * (rec.retention_percent or 0.0) / 100.0
            rec.amount_gross = gross
            rec.retention_amount = retention
            rec.amount_net = gross - retention

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            self.retention_percent = self.contract_id.retention_percent

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.construction.ipc') or _('New')
            if not vals.get('retention_percent') and vals.get('contract_id'):
                contract = self.env['sa.construction.contract'].browse(
                    vals['contract_id'])
                vals['retention_percent'] = contract.retention_percent
        return super().create(vals_list)

    def _check_over_certification(self):
        """Block certifying more than the remaining BOQ quantity."""
        precision = self.env['decimal.precision'].precision_get(
            'Product Unit of Measure')
        for rec in self:
            per_boq = {}
            for line in rec.line_ids:
                per_boq.setdefault(line.boq_line_id, 0.0)
                per_boq[line.boq_line_id] += line.quantity
            for boq, qty in per_boq.items():
                remaining = boq.qty_remaining
                if float_compare(qty, remaining, precision_digits=precision) > 0:
                    raise UserError(_(
                        "Certified quantity %(qty)s for '%(item)s' exceeds the "
                        "remaining %(rem)s on the bill of quantities.",
                        qty=qty, item=boq.name, rem=remaining))

    def action_approve(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.line_ids:
                raise UserError(_(
                    "Add at least one certified work line before approving."))
            rec._check_over_certification()
            rec.state = 'approved'
            if rec.contract_id.state == 'confirmed':
                rec.contract_id.state = 'in_progress'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.bill_id:
                raise UserError(_(
                    "Cancel the vendor bill before resetting this "
                    "certificate to draft."))
            rec.state = 'draft'

    def _prepare_bill_line_vals(self, analytic_distribution):
        self.ensure_one()
        lines = []
        for line in self.line_ids:
            lines.append((0, 0, {
                'name': '%s - %s' % (self.name, line.name or ''),
                'product_id': line.product_id.id or False,
                'quantity': line.quantity,
                'price_unit': line.unit_rate,
                'analytic_distribution': analytic_distribution,
            }))
        return lines

    def _prepare_bill_vals(self, analytic_distribution):
        self.ensure_one()
        return {
            'move_type': 'in_invoice',
            'partner_id': self.contractor_id.id,
            'invoice_date': self.date,
            'date': self.date,
            'ref': self.name,
            'invoice_origin': self.contract_id.name,
            'company_id': self.company_id.id,
            'invoice_line_ids': self._prepare_bill_line_vals(analytic_distribution),
        }

    def action_create_bill(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_(
                "Only approved certificates can be billed."))
        if self.bill_id:
            raise UserError(_("A vendor bill already exists for this certificate."))
        if not self.line_ids:
            raise UserError(_("Nothing to bill on this certificate."))

        analytic = self.construction_id._ensure_analytic_account()
        distribution = {str(analytic.id): 100}
        move = self.env['account.move'].create(
            self._prepare_bill_vals(distribution))

        # In Odoo 18 a bill line with a product recomputes ``price_unit`` from the
        # product's sales price and injects default taxes. Force the certified
        # rate and strip taxes so the cost equals the certified work value.
        fallback_account = False
        bill_lines = move.invoice_line_ids
        for move_line, ipc_line in zip(bill_lines, self.line_ids):
            move_line.tax_ids = [(5, 0, 0)]
            move_line.price_unit = ipc_line.unit_rate
            if not move_line.account_id:
                if not fallback_account:
                    fallback_account = self.env['account.account'].search(
                        [('account_type', '=', 'expense')], limit=1)
                move_line.account_id = fallback_account

        self.bill_id = move
        self.state = 'billed'
        return self.action_view_bill()

    def action_view_bill(self):
        self.ensure_one()
        if not self.bill_id:
            raise UserError(_("No vendor bill is linked to this certificate."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bill'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.bill_id.id,
            'target': 'current',
        }


class SaConstructionIpcLine(models.Model):
    _name = 'sa.construction.ipc.line'
    _description = 'Interim Payment Certificate Line'
    _order = 'ipc_id, sequence, id'

    ipc_id = fields.Many2one(
        'sa.construction.ipc', string='Certificate',
        required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    boq_line_id = fields.Many2one(
        'sa.construction.boq.line', string='BoQ Item', required=True,
        domain="[('contract_id', '=', parent.contract_id)]")
    name = fields.Char(string='Description')
    product_id = fields.Many2one(
        'product.product', related='boq_line_id.product_id', store=True)
    uom_id = fields.Many2one('uom.uom', related='boq_line_id.uom_id', store=True)
    unit_rate = fields.Monetary(
        string='Rate', related='boq_line_id.unit_rate', store=True)
    quantity = fields.Float(
        string='Qty This Period', default=0.0,
        digits='Product Unit of Measure')
    amount = fields.Monetary(string='Amount', compute='_compute_amount', store=True)
    currency_id = fields.Many2one(
        related='ipc_id.currency_id', store=True)
    qty_remaining = fields.Float(
        string='Remaining', related='boq_line_id.qty_remaining')

    @api.depends('quantity', 'unit_rate')
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.unit_rate

    @api.onchange('boq_line_id')
    def _onchange_boq_line_id(self):
        if self.boq_line_id:
            self.name = self.boq_line_id.name
            if not self.quantity:
                self.quantity = self.boq_line_id.qty_remaining
