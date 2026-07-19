# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class TestBookingWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer',
            'sa_cnic': '11111-1111111-1',
        })
        cls.project = cls.env['sa.property.project'].create({
            'name': 'Test Society',
            'code': 'TST-SOC',
            'city': 'Lahore',
            'total_area': 100,
            'area_uom': 'kanal',
        })
        cls.property = cls.env['sa.property'].create({
            'name': '5 Marla Plot',
            'project_id': cls.project.id,
            'property_type': 'plot',
            'area': 5,
            'area_uom': 'marla',
            'base_price': 5000000.0,
            'state': 'available',
        })
        cls.plan = cls.env['sa.payment.plan'].create({
            'name': 'Test Plan',
            'down_payment_percent': 20.0,
            'installment_count': 12,
            'frequency': 'monthly',
            'on_possession_percent': 0.0,
        })

    def _create_booking(self):
        return self.env['sa.property.booking'].create({
            'customer_id': self.partner.id,
            'property_id': self.property.id,
            'booking_date': date(2025, 1, 1),
            'total_price': 5000000.0,
            'payment_plan_id': self.plan.id,
        })

    def test_create_booking_with_sequence(self):
        booking = self._create_booking()
        self.assertTrue(booking.name.startswith('BKG-'))
        self.assertEqual(booking.state, 'draft')

    def test_confirm_generates_schedule_and_invoice(self):
        booking = self._create_booking()
        booking.action_confirm()
        self.assertIn(booking.state, ('confirmed', 'in_payment'))
        self.assertEqual(self.property.state, 'booked')
        self.assertEqual(len(booking.installment_ids), 13)  # 1 down + 12
        self.assertAlmostEqual(
            sum(booking.installment_ids.mapped('amount')),
            booking.total_price, places=2)
        # First installment got an invoice
        first = booking.installment_ids.sorted('sequence')[0]
        self.assertTrue(first.invoice_id)

    def test_cannot_double_book_same_property(self):
        booking1 = self._create_booking()
        booking1.action_confirm()
        booking2 = self.env['sa.property.booking'].create({
            'customer_id': self.partner.id,
            'property_id': self.property.id,
            'booking_date': date(2025, 1, 1),
            'total_price': 5000000.0,
            'payment_plan_id': self.plan.id,
        })
        with self.assertRaises(ValidationError):
            booking2.action_confirm()

    def test_cancel_releases_property(self):
        booking = self._create_booking()
        booking.action_confirm()
        # Cancel only works if no posted invoices; the auto-generated invoice
        # is still in draft so cancel should succeed.
        booking.action_cancel()
        self.assertEqual(booking.state, 'cancelled')
        self.assertEqual(self.property.state, 'available')
        self.assertEqual(len(booking.installment_ids), 0)

    def test_past_due_first_installment_is_invoiced(self):
        """A down payment due before today must still get an invoice on
        confirm. Regression: the first-due installment computes to 'overdue'
        (not 'pending') once its due date has passed, so invoice generation
        must not be restricted to 'pending' installments only."""
        booking = self.env['sa.property.booking'].create({
            'customer_id': self.partner.id,
            'property_id': self.property.id,
            'booking_date': date.today() - timedelta(days=400),
            'total_price': 5000000.0,
            'payment_plan_id': self.plan.id,
        })
        booking.action_confirm()
        first = booking.installment_ids.sorted('sequence')[0]
        self.assertTrue(
            first.invoice_id,
            "Past-due first installment should still be invoiced on confirm.")
        # With a draft invoice attached it moves to 'invoiced', not 'overdue'.
        self.assertEqual(first.state, 'invoiced')

