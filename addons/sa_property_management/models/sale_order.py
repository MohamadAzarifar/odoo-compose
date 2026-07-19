# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sa_booking_id = fields.Many2one(
        'sa.property.booking', string='Property Booking', copy=False, index=True,
        help="Property booking that generated this sale order.")

    def _create_invoices(self, *args, **kwargs):
        """Property orders are invoiced exclusively through the booking's
        installment schedule. Blocking direct order invoicing prevents the
        duplicate revenue that arises when the order is invoiced for the full
        price on top of the installment invoices.
        """
        booking_orders = self.filtered('sa_booking_id')
        if booking_orders:
            raise UserError(_(
                "Property sale orders are invoiced through the booking's "
                "installment schedule, not directly from the order.\n\n"
                "Open booking %s and generate the down-payment / installment "
                "invoices from there instead.",
                ", ".join(booking_orders.mapped('sa_booking_id.name')),
            ))
        return super()._create_invoices(*args, **kwargs)
