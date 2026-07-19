# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPaymentPlan(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plan = cls.env['sa.payment.plan'].create({
            'name': 'Test 24-month plan',
            'down_payment_percent': 25.0,
            'installment_count': 24,
            'frequency': 'monthly',
            'on_possession_percent': 5.0,
        })

    def test_schedule_sums_to_total(self):
        total = 12000000.0  # 1.2 crore PKR
        schedule = self.plan.generate_schedule(total, date(2025, 1, 1))
        # 1 down + 24 installments + 1 on_possession = 26
        self.assertEqual(len(schedule), 26)
        total_sum = sum(line['amount'] for line in schedule)
        self.assertAlmostEqual(total_sum, total, places=2)

    def test_schedule_with_balloon(self):
        self.env['sa.payment.plan.line'].create({
            'plan_id': self.plan.id,
            'name': 'Balloon',
            'after_installment': 12,
            'percent': 5.0,
        })
        schedule = self.plan.generate_schedule(10000000.0, date(2025, 1, 1))
        # 1 down + 24 installments + 1 balloon + 1 on_possession = 27
        self.assertEqual(len(schedule), 27)
        balloon = [line for line in schedule if line['line_type'] == 'extra']
        self.assertEqual(len(balloon), 1)
        self.assertAlmostEqual(balloon[0]['amount'], 500000.0, places=2)

    def test_total_percent_validation(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env['sa.payment.plan'].create({
                'name': 'Bad plan',
                'down_payment_percent': 90.0,
                'on_possession_percent': 30.0,  # 120% > 100
                'installment_count': 10,
            })
