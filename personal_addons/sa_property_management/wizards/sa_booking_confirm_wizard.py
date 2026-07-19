# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaBookingConfirmWizard(models.TransientModel):
    """Preview the installment schedule before confirming a booking."""
    _name = 'sa.booking.confirm.wizard'
    _description = 'Confirm Booking Wizard'

    booking_id = fields.Many2one(
        'sa.property.booking', required=True, ondelete='cascade')
    payment_plan_id = fields.Many2one(
        'sa.payment.plan', required=True)
    total_price = fields.Monetary(currency_field='currency_id', required=True)
    booking_date = fields.Date(required=True)
    currency_id = fields.Many2one(related='booking_id.currency_id', readonly=True)

    preview_line_ids = fields.One2many(
        'sa.booking.confirm.wizard.line', 'wizard_id',
        string='Preview Schedule')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        booking_id = self.env.context.get('default_booking_id') \
            or self.env.context.get('active_id')
        if booking_id and self.env.context.get('active_model') == 'sa.property.booking':
            booking = self.env['sa.property.booking'].browse(booking_id)
            res.update({
                'booking_id': booking.id,
                'payment_plan_id': booking.payment_plan_id.id,
                'total_price': booking.total_price,
                'booking_date': booking.booking_date,
            })
        return res

    @api.onchange('payment_plan_id', 'total_price', 'booking_date')
    def _onchange_recompute_preview(self):
        self.preview_line_ids = [(5, 0, 0)]
        if not (self.payment_plan_id and self.total_price and self.booking_date):
            return
        schedule = self.payment_plan_id.generate_schedule(
            self.total_price, self.booking_date)
        self.preview_line_ids = [
            (0, 0, {
                'sequence': e['sequence'],
                'name': e['name'],
                'due_date': e['due_date'],
                'amount': e['amount'],
                'line_type': e['line_type'],
            }) for e in schedule
        ]

    def action_confirm(self):
        self.ensure_one()
        if not self.booking_id:
            raise UserError(_("No booking attached."))
        self.booking_id.write({
            'payment_plan_id': self.payment_plan_id.id,
            'total_price': self.total_price,
            'booking_date': self.booking_date,
        })
        self.booking_id.action_confirm()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sa.property.booking',
            'res_id': self.booking_id.id,
            'view_mode': 'form',
        }


class SaBookingConfirmWizardLine(models.TransientModel):
    _name = 'sa.booking.confirm.wizard.line'
    _description = 'Confirm Booking Wizard Preview Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'sa.booking.confirm.wizard', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='wizard_id.currency_id', readonly=True)
    sequence = fields.Integer()
    name = fields.Char()
    due_date = fields.Date()
    amount = fields.Monetary(currency_field='currency_id')
    line_type = fields.Selection(
        [('down_payment', 'Down Payment'),
         ('installment', 'Installment'),
         ('extra', 'Extra'),
         ('on_possession', 'On Possession')])
