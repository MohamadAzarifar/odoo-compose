# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaPropertySurrenderWizard(models.TransientModel):
    """Surrender a booked unit back to the company.

    Cancels the active booking, optionally issues a customer refund (credit
    note) for amounts already paid less any forfeiture, and returns the unit
    to the available pool.
    """
    _name = 'sa.property.surrender.wizard'
    _description = 'Property Surrender'

    property_id = fields.Many2one(
        'sa.property', required=True, domain=[('state', '=', 'booked')])
    booking_id = fields.Many2one(
        'sa.property.booking', string='Booking', required=True)
    customer_id = fields.Many2one(
        'res.partner', related='booking_id.customer_id', readonly=True)
    surrender_date = fields.Date(
        required=True, default=fields.Date.context_today)
    amount_paid = fields.Monetary(
        currency_field='currency_id', readonly=True,
        help="Amount the customer has paid against this booking so far.")
    deduction_amount = fields.Monetary(
        string='Forfeiture', currency_field='currency_id',
        help="Amount retained by the company (cancellation charges).")
    refund_amount = fields.Monetary(
        currency_field='currency_id',
        help="Amount refunded to the customer via a credit note.")
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    create_refund = fields.Boolean(
        string='Create Refund', default=True,
        help="Raise a customer credit note for the refund amount.")
    note = fields.Char()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        prop_id = self.env.context.get('default_property_id') \
            or (self.env.context.get('active_model') == 'sa.property'
                and self.env.context.get('active_id'))
        if prop_id:
            prop = self.env['sa.property'].browse(prop_id)
            booking = self.env['sa.property.booking'].search([
                ('property_id', '=', prop.id),
                ('state', 'in', ('confirmed', 'in_payment')),
            ], order='booking_date desc', limit=1)
            paid = booking.amount_paid if booking else 0.0
            res.update({
                'property_id': prop.id,
                'booking_id': booking.id,
                'currency_id': prop.currency_id.id,
                'amount_paid': paid,
                'refund_amount': paid,
            })
        return res

    @api.onchange('deduction_amount', 'amount_paid')
    def _onchange_deduction(self):
        self.refund_amount = max(self.amount_paid - self.deduction_amount, 0.0)

    def action_confirm(self):
        self.ensure_one()
        prop = self.property_id
        booking = self.booking_id
        if prop.state != 'booked':
            raise UserError(_("Surrender applies to booked units only."))
        if not booking:
            raise UserError(_(
                "No active booking found for this unit to surrender."))

        refund = False
        if self.create_refund and self.refund_amount > 0:
            refund = self._create_customer_refund()

        booking._cancel_for_surrender()
        prop.message_post(body=_(
            "Unit surrendered by %(customer)s on %(date)s. "
            "Refund: %(refund)s, forfeiture: %(deduction)s.",
            customer=self.customer_id.display_name,
            date=self.surrender_date,
            refund=self.refund_amount,
            deduction=self.deduction_amount,
        ))
        prop._reset_to_available(restock=True)

        if refund:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Surrender Refund'),
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': refund.id,
            }
        return {'type': 'ir.actions.act_window_close'}

    def _create_customer_refund(self):
        self.ensure_one()
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            raise UserError(_("No sales journal found."))
        product = self.property_id.product_id
        line_vals = {
            'quantity': 1.0,
            'price_unit': self.refund_amount,
            'name': self.note or _(
                'Surrender refund: %s') % self.property_id.display_name,
        }
        if product:
            line_vals['product_id'] = product.id
        refund = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.customer_id.id,
            'invoice_date': self.surrender_date,
            'journal_id': journal.id,
            'currency_id': self.currency_id.id,
            'sa_booking_id': self.booking_id.id,
            'invoice_line_ids': [(0, 0, line_vals)],
        })
        # The product line recomputes price/taxes from the product; force the
        # agreed refund amount as the exact credit-note total.
        line = refund.invoice_line_ids[:1]
        if line:
            line.tax_ids = [(5, 0, 0)]
            line.price_unit = self.refund_amount
        return refund
