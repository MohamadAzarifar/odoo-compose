# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaConstructionMaterialIssue(models.Model):
    _name = 'sa.construction.material.issue'
    _description = 'Construction Material Issue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Issue', required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'), tracking=True)
    construction_id = fields.Many2one(
        'sa.construction.project', string='Construction Project',
        required=True, ondelete='cascade', index=True, tracking=True)
    company_id = fields.Many2one(
        related='construction_id.company_id', store=True)
    currency_id = fields.Many2one(
        related='construction_id.currency_id', store=True)
    date = fields.Date(
        string='Issue Date', default=fields.Date.context_today,
        required=True, tracking=True)
    notes = fields.Html(string='Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Issued'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)

    line_ids = fields.One2many(
        'sa.construction.material.issue.line', 'issue_id', string='Materials')
    picking_id = fields.Many2one(
        'stock.picking', string='Transfer', readonly=True, copy=False)
    amount_total = fields.Monetary(
        string='Total Cost', compute='_compute_amount_total', store=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)',
         'The material issue reference must be unique per company.'),
    ]

    @api.depends('line_ids.amount')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.construction.material.issue') or _('New')
        return super().create(vals_list)

    def _get_source_location(self):
        self.ensure_one()
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if warehouse:
            return warehouse.lot_stock_id
        return self.env['stock.location'].search(
            [('usage', '=', 'internal')], limit=1)

    def _create_picking(self):
        self.ensure_one()
        source = self._get_source_location()
        dest = self.construction_id._ensure_site_location()
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        picking_type = warehouse.int_type_id if warehouse else \
            self.env['stock.picking.type'].search(
                [('code', '=', 'internal')], limit=1)
        if picking_type and not picking_type.active:
            picking_type.sudo().active = True
        if not picking_type:
            raise UserError(_(
                "No internal transfer operation type is configured in the "
                "warehouse."))
        # v19 dropped stock.move.name in favour of description_picking.
        move_fields = self.env['stock.move']._fields
        desc_field = 'name' if 'name' in move_fields else 'description_picking'
        move_cmds = []
        for line in self.line_ids:
            if not line.product_id:
                continue
            move_vals = {
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.uom_id.id or line.product_id.uom_id.id,
                'location_id': source.id,
                'location_dest_id': dest.id,
            }
            move_vals[desc_field] = line.product_id.display_name
            move_cmds.append((0, 0, move_vals))
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source.id,
            'location_dest_id': dest.id,
            'origin': self.name,
            'company_id': self.company_id.id,
            'move_ids': move_cmds,
        })
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.with_context(skip_backorder=True).button_validate()
        return picking

    def _create_cost_entries(self):
        self.ensure_one()
        analytic = self.construction_id._ensure_analytic_account()
        AAL = self.env['account.analytic.line'].sudo()
        for line in self.line_ids:
            if not line.amount:
                continue
            AAL.create({
                'name': '%s: %s' % (self.name, line.product_id.display_name),
                'account_id': analytic.id,
                'amount': -line.amount,
                'unit_amount': line.quantity,
                'product_id': line.product_id.id,
                'company_id': self.company_id.id,
                'date': self.date,
                'ref': self.name,
            })

    def action_issue(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.line_ids:
                raise UserError(_(
                    "Add at least one material line before issuing."))
            rec._create_cost_entries()
            rec.picking_id = rec._create_picking()
            rec.state = 'done'

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("No transfer is linked to this issue."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transfer'),
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
            'target': 'current',
        }


class SaConstructionMaterialIssueLine(models.Model):
    _name = 'sa.construction.material.issue.line'
    _description = 'Construction Material Issue Line'
    _order = 'issue_id, sequence, id'

    issue_id = fields.Many2one(
        'sa.construction.material.issue', string='Material Issue',
        required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        domain="[('is_storable', '=', True)]")
    name = fields.Char(string='Description')
    uom_id = fields.Many2one('uom.uom', string='Unit')
    quantity = fields.Float(
        string='Quantity', default=1.0, digits='Product Unit of Measure')
    unit_cost = fields.Monetary(
        string='Unit Cost', compute='_compute_unit_cost', store=True, readonly=False)
    amount = fields.Monetary(string='Cost', compute='_compute_amount', store=True)
    currency_id = fields.Many2one(
        related='issue_id.currency_id', store=True)

    @api.depends('product_id')
    def _compute_unit_cost(self):
        for line in self:
            line.unit_cost = line.product_id.standard_price

    @api.depends('quantity', 'unit_cost')
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.unit_cost

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
