# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaPropertyBuybackWizard(models.TransientModel):
    """Buy a sold/transferred unit back from its current owner.

    Optionally raises a vendor bill to the owner for the agreed buy-back
    amount, then returns the unit to the available pool.
    """
    _name = 'sa.property.buyback.wizard'
    _description = 'Property Buy-Back'

    property_id = fields.Many2one(
        'sa.property', required=True,
        domain=[('state', 'in', ('sold', 'transferred'))])
    partner_id = fields.Many2one(
        'res.partner', string='Seller (Current Owner)', required=True,
        help="Party the company buys the unit back from.")
    buyback_date = fields.Date(
        required=True, default=fields.Date.context_today)
    buyback_amount = fields.Monetary(
        currency_field='currency_id', required=True,
        help="Amount payable to the current owner for the buy-back.")
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    create_bill = fields.Boolean(
        string='Create Vendor Bill', default=True,
        help="Raise a vendor bill to the owner for the buy-back amount.")
    note = fields.Char()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        prop_id = self.env.context.get('default_property_id') \
            or (self.env.context.get('active_model') == 'sa.property'
                and self.env.context.get('active_id'))
        if prop_id:
            prop = self.env['sa.property'].browse(prop_id)
            res.update({
                'property_id': prop.id,
                'partner_id': prop.current_owner_id.id,
                'buyback_amount': prop.base_price,
                'currency_id': prop.currency_id.id,
            })
        return res

    @api.onchange('property_id')
    def _onchange_property_id(self):
        if self.property_id:
            self.partner_id = self.property_id.current_owner_id
            self.buyback_amount = self.property_id.base_price
            self.currency_id = self.property_id.currency_id

    def action_confirm(self):
        self.ensure_one()
        prop = self.property_id
        if prop.state not in ('sold', 'transferred'):
            raise UserError(_(
                "Buy-back applies to sold or transferred units only."))
        if not self.partner_id:
            raise UserError(_("Set the current owner to pay."))

        bill = False
        if self.create_bill and self.buyback_amount > 0:
            bill = self._create_vendor_bill()

        prop.message_post(body=_(
            "Unit bought back from %(owner)s for %(amount)s on %(date)s.",
            owner=self.partner_id.display_name,
            amount=self.buyback_amount,
            date=self.buyback_date,
        ))
        prop._reset_to_available(restock=True)

        if bill:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Buy-Back Bill'),
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': bill.id,
            }
        return {'type': 'ir.actions.act_window_close'}

    def _create_vendor_bill(self):
        self.ensure_one()
        if self.partner_id.supplier_rank < 1:
            self.partner_id.supplier_rank = 1
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            raise UserError(_("No purchase journal found."))
        product = self.property_id.product_id
        line_vals = {
            'quantity': 1.0,
            'price_unit': self.buyback_amount,
            'name': self.note or _('Buy-back: %s') % self.property_id.display_name,
        }
        if product:
            line_vals['product_id'] = product.id
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.buyback_date,
            'journal_id': journal.id,
            'currency_id': self.currency_id.id,
            'invoice_line_ids': [(0, 0, line_vals)],
        })
        # The product line recomputes price/taxes from the product; force the
        # agreed buy-back amount as the exact bill total.
        line = bill.invoice_line_ids[:1]
        if line:
            line.tax_ids = [(5, 0, 0)]
            line.price_unit = self.buyback_amount
        return bill
