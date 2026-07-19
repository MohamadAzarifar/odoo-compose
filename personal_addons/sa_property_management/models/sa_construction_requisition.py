# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaConstructionRequisition(models.Model):
    _name = 'sa.construction.requisition'
    _description = 'Material Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Requisition', required=True, copy=False, readonly=True,
        index=True, default=lambda self: _('New'), tracking=True)
    construction_id = fields.Many2one(
        'sa.construction.project', string='Construction Project',
        required=True, ondelete='cascade', index=True, tracking=True)
    company_id = fields.Many2one(
        related='construction_id.company_id', store=True)
    currency_id = fields.Many2one(
        related='construction_id.currency_id', store=True)
    requested_by = fields.Many2one(
        'res.users', string='Requested By', default=lambda self: self.env.user)
    vendor_id = fields.Many2one(
        'res.partner', string='Preferred Vendor',
        help="Vendor used when raising the request for quotation.")
    date_request = fields.Date(
        string='Request Date', default=fields.Date.context_today, tracking=True)
    date_required = fields.Date(string='Required By')
    notes = fields.Html(string='Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('purchased', 'Purchased'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)

    line_ids = fields.One2many(
        'sa.construction.requisition.line', 'requisition_id', string='Items')
    purchase_order_ids = fields.One2many(
        'purchase.order', 'sa_requisition_id', string='Purchase Orders')

    estimated_cost = fields.Monetary(
        string='Estimated Cost', compute='_compute_estimated', store=True)
    po_count = fields.Integer(compute='_compute_po_count')

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)',
         'The requisition reference must be unique per company.'),
    ]

    @api.depends('line_ids.estimated_cost')
    def _compute_estimated(self):
        for rec in self:
            rec.estimated_cost = sum(rec.line_ids.mapped('estimated_cost'))

    def _compute_po_count(self):
        for rec in self:
            rec.po_count = len(rec.purchase_order_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.construction.requisition') or _('New')
        return super().create(vals_list)

    def action_approve(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_(
                    "Add at least one item before approving the requisition."))
            rec.state = 'approved'

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_create_rfq(self):
        self.ensure_one()
        if self.state not in ('approved', 'purchased'):
            raise UserError(_(
                "Approve the requisition before raising a purchase order."))
        if not self.vendor_id:
            raise UserError(_(
                "Set a preferred vendor before raising a purchase order."))
        if not self.line_ids:
            raise UserError(_("There is nothing to purchase."))

        # v19 renamed purchase.order.line.product_uom -> product_uom_id.
        pol_fields = self.env['purchase.order.line']._fields
        uom_field = 'product_uom_id' if 'product_uom_id' in pol_fields \
            else 'product_uom'
        order_lines = []
        for line in self.line_ids:
            line_vals = {
                'product_id': line.product_id.id,
                'name': line.name or line.product_id.display_name,
                'product_qty': line.quantity,
                'price_unit': line.product_id.standard_price,
                'date_planned': fields.Datetime.now(),
            }
            line_vals[uom_field] = (
                line.uom_id.id or line.product_id.uom_po_id.id)
            order_lines.append((0, 0, line_vals))
        # Note: procurement does not carry the construction analytic account.
        # Buying material only replenishes stock; the project cost is booked
        # later when the material is issued to the site.
        order = self.env['purchase.order'].create({
            'partner_id': self.vendor_id.id,
            'origin': self.name,
            'sa_requisition_id': self.id,
            'company_id': self.company_id.id,
            'order_line': order_lines,
        })
        self.state = 'purchased'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request for Quotation'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': order.id,
            'target': 'current',
        }

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('sa_requisition_id', '=', self.id)],
        }


class SaConstructionRequisitionLine(models.Model):
    _name = 'sa.construction.requisition.line'
    _description = 'Material Requisition Line'
    _order = 'requisition_id, sequence, id'

    requisition_id = fields.Many2one(
        'sa.construction.requisition', string='Requisition',
        required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        'product.product', string='Product', required=True)
    name = fields.Char(string='Description')
    uom_id = fields.Many2one('uom.uom', string='Unit')
    quantity = fields.Float(
        string='Quantity', default=1.0, digits='Product Unit of Measure')
    currency_id = fields.Many2one(
        related='requisition_id.currency_id', store=True)
    estimated_cost = fields.Monetary(
        string='Estimated Cost', compute='_compute_estimated_cost', store=True)

    @api.depends('quantity', 'product_id')
    def _compute_estimated_cost(self):
        for line in self:
            line.estimated_cost = line.quantity * line.product_id.standard_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
