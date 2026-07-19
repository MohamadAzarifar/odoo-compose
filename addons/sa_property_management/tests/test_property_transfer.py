# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestPropertyTransfer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # CVT and other preset taxes are tagged for Pakistan; point the company's
        # operating country there so the country-aware engine applies them.
        cls.env.company.sa_operating_country_id = cls.env.ref('base.pk')
        cls.seller = cls.env['res.partner'].create({'name': 'Seller', 'sa_cnic': '22222-2222222-2'})
        cls.buyer = cls.env['res.partner'].create({'name': 'Buyer', 'sa_cnic': '33333-3333333-3'})
        cls.project = cls.env['sa.property.project'].create({
            'name': 'Transfer Test Society',
            'code': 'TST-TRF',
            'total_area': 50, 'area_uom': 'kanal',
        })
        cls.property = cls.env['sa.property'].create({
            'name': '1 Kanal House',
            'project_id': cls.project.id,
            'property_type': 'house',
            'area': 1, 'area_uom': 'kanal',
            'base_price': 30000000.0,
            'dc_value': 25000000.0,
            'state': 'sold',
            'current_owner_id': cls.seller.id,
        })

    def test_distinct_parties_required(self):
        with self.assertRaises(ValidationError):
            self.env['sa.property.transfer'].create({
                'property_id': self.property.id,
                'from_partner_id': self.seller.id,
                'to_partner_id': self.seller.id,
                'transfer_date': date(2025, 6, 1),
                'sale_price': 30000000.0,
            })

    def test_apply_default_taxes_uses_dc_value(self):
        # Ensure at least one tax is configured (demo data is noupdate so this
        # is safe even when re-running tests)
        tax = self.env.ref('sa_property_management.tax_cvt', raise_if_not_found=False)
        self.assertTrue(tax, "Demo tax CVT should be present")
        transfer = self.env['sa.property.transfer'].create({
            'property_id': self.property.id,
            'from_partner_id': self.seller.id,
            'to_partner_id': self.buyer.id,
            'transfer_date': date(2025, 6, 1),
            'sale_price': 30000000.0,
            'dc_value': 25000000.0,
        })
        transfer.action_apply_default_taxes()
        self.assertTrue(transfer.tax_line_ids)
        # CVT 2% of DC value (25,000,000) = 500,000
        cvt_line = transfer.tax_line_ids.filtered(lambda l: l.tax_id == tax)
        self.assertAlmostEqual(cvt_line.amount, 500000.0, places=2)

    def test_totals_split_by_payer(self):
        transfer = self.env['sa.property.transfer'].create({
            'property_id': self.property.id,
            'from_partner_id': self.seller.id,
            'to_partner_id': self.buyer.id,
            'transfer_date': date(2025, 6, 1),
            'sale_price': 30000000.0,
            'dc_value': 25000000.0,
        })
        transfer.action_apply_default_taxes()
        self.assertGreater(transfer.total_buyer, transfer.sale_price)
        self.assertLess(transfer.net_to_seller, transfer.sale_price)
