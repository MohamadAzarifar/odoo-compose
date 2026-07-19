# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, UserError, ValidationError


@tagged('post_install', '-at_install')
class TestPenaltyKibor(TransactionCase):
    """Phase 7: late-penalty computation and KIBOR rate lookup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['sa.kibor.rate'].create([
            {'effective_date': date.today() - timedelta(days=30),
             'tenor': '6m', 'rate': 12.0},
            {'effective_date': date.today() - timedelta(days=400),
             'tenor': '6m', 'rate': 20.5},
        ])

    def test_get_rate_for_returns_most_recent(self):
        Rate = self.env['sa.kibor.rate']
        self.assertEqual(Rate.get_rate_for(date.today(), '6m'), 12.0)
        old = Rate.get_rate_for(date.today() - timedelta(days=200), '6m')
        self.assertEqual(old, 20.5)

    def test_get_rate_for_missing_returns_zero(self):
        self.assertEqual(
            self.env['sa.kibor.rate'].get_rate_for(date.today(), '12m'), 0.0)

    def test_penalty_flat(self):
        plan = self.env['sa.payment.plan'].create({
            'name': 'Flat Penalty', 'down_payment_percent': 10.0,
            'installment_count': 4, 'frequency': 'monthly',
            'penalty_type': 'flat', 'penalty_value': 500.0})
        # 25 days late, no grace -> 500 * 25
        self.assertAlmostEqual(
            plan.compute_penalty(100000.0, 25), 12500.0, places=2)

    def test_penalty_percent(self):
        plan = self.env['sa.payment.plan'].create({
            'name': 'Pct Penalty', 'down_payment_percent': 10.0,
            'installment_count': 4, 'frequency': 'monthly',
            'penalty_type': 'percent', 'penalty_value': 0.05})
        # 0.05% per day of 100,000 over 10 days
        self.assertAlmostEqual(
            plan.compute_penalty(100000.0, 10), 500.0, places=2)

    def test_penalty_kibor(self):
        plan = self.env['sa.payment.plan'].create({
            'name': 'Kibor Penalty', 'down_payment_percent': 10.0,
            'installment_count': 4, 'frequency': 'monthly',
            'penalty_type': 'kibor', 'penalty_kibor_tenor': '6m',
            'penalty_kibor_spread': 3.0})
        # (12 + 3)% annual on 100,000 for 10 days / 365
        expected = 100000.0 * 0.15 / 365 * 10
        self.assertAlmostEqual(
            plan.compute_penalty(100000.0, 10), round(expected, 2), places=2)

    def test_penalty_grace_period(self):
        plan = self.env['sa.payment.plan'].create({
            'name': 'Grace Penalty', 'down_payment_percent': 10.0,
            'installment_count': 4, 'frequency': 'monthly',
            'penalty_type': 'flat', 'penalty_value': 500.0,
            'penalty_grace_days': 10})
        # 8 days late, fully within grace -> 0
        self.assertEqual(plan.compute_penalty(100000.0, 8), 0.0)
        # 15 days late, 5 chargeable -> 500 * 5
        self.assertAlmostEqual(
            plan.compute_penalty(100000.0, 15), 2500.0, places=2)

    def test_penalty_none(self):
        plan = self.env['sa.payment.plan'].create({
            'name': 'No Penalty', 'down_payment_percent': 10.0,
            'installment_count': 4, 'frequency': 'monthly',
            'penalty_type': 'none'})
        self.assertEqual(plan.compute_penalty(100000.0, 30), 0.0)


@tagged('post_install', '-at_install')
class TestPropertyDocument(TransactionCase):
    """Phase 10: property documentation model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['sa.property.project'].create({
            'name': 'Doc Society', 'code': 'DOC-SOC',
            'total_area': 50, 'area_uom': 'kanal'})
        cls.property = cls.env['sa.property'].create({
            'name': 'Doc Plot', 'project_id': cls.project.id,
            'property_type': 'plot', 'area': 5, 'area_uom': 'marla',
            'base_price': 5000000.0, 'state': 'available'})
        cls.partner = cls.env['res.partner'].create({'name': 'Doc Owner'})

    def test_document_sequence(self):
        doc = self.env['sa.property.document'].create({
            'document_type': 'allotment_letter',
            'property_id': self.property.id})
        self.assertTrue(doc.name.startswith('DOC-'))

    def test_document_count_rollup(self):
        self.env['sa.property.document'].create({
            'document_type': 'noc', 'property_id': self.property.id})
        self.assertEqual(self.property.document_count, 1)

    def test_mark_issued_sets_date(self):
        doc = self.env['sa.property.document'].create({
            'document_type': 'ndc', 'property_id': self.property.id})
        doc.action_mark_issued()
        self.assertEqual(doc.state, 'issued')
        self.assertTrue(doc.issue_date)

    def test_is_expired_compute(self):
        past = self.env['sa.property.document'].create({
            'document_type': 'noc', 'property_id': self.property.id,
            'state': 'issued', 'expiry_date': date.today() - timedelta(days=1)})
        self.assertTrue(past.is_expired)
        future = self.env['sa.property.document'].create({
            'document_type': 'ndc', 'property_id': self.property.id,
            'state': 'issued', 'expiry_date': date.today() + timedelta(days=10)})
        self.assertFalse(future.is_expired)

    def test_date_constraint(self):
        with self.assertRaises(ValidationError):
            self.env['sa.property.document'].create({
                'document_type': 'other', 'property_id': self.property.id,
                'issue_date': date.today(),
                'expiry_date': date.today() - timedelta(days=5)})


@tagged('post_install', '-at_install')
class TestTransferDocumentation(TransactionCase):
    """Phase 11: transfer documentation checklist + completion gate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.seller = cls.env['res.partner'].create({'name': 'TR Seller'})
        cls.buyer = cls.env['res.partner'].create({'name': 'TR Buyer'})
        cls.project = cls.env['sa.property.project'].create({
            'name': 'TR Society', 'code': 'TR-SOC',
            'total_area': 50, 'area_uom': 'kanal'})
        cls.property = cls.env['sa.property'].create({
            'name': 'TR Plot', 'project_id': cls.project.id,
            'property_type': 'plot', 'area': 5, 'area_uom': 'marla',
            'base_price': 9000000.0, 'state': 'sold',
            'current_owner_id': cls.seller.id})

    def _transfer(self):
        return self.env['sa.property.transfer'].create({
            'property_id': self.property.id,
            'from_partner_id': self.seller.id,
            'to_partner_id': self.buyer.id,
            'transfer_date': date.today(),
            'sale_price': 9000000.0})

    def test_load_default_checklist_idempotent(self):
        trf = self._transfer()
        trf.action_load_default_checklist()
        first = trf.checklist_total
        self.assertEqual(first, 10)
        trf.action_load_default_checklist()
        self.assertEqual(trf.checklist_total, first)

    def test_checklist_progress(self):
        trf = self._transfer()
        trf.action_load_default_checklist()
        self.assertEqual(trf.checklist_progress, 0.0)
        self.assertFalse(trf.checklist_complete)
        trf.checklist_ids.write({'is_done': True})
        trf.invalidate_recordset()
        self.assertEqual(trf.checklist_progress, 100.0)
        self.assertTrue(trf.checklist_complete)

    def test_completion_gate_blocks_pending(self):
        trf = self._transfer()
        trf.action_load_default_checklist()
        trf.state = 'approved'
        with self.assertRaises(UserError):
            trf.action_complete()

    def test_completion_without_checklist_allowed(self):
        # No checklist => gate is bypassed (backward compatible).
        trf = self._transfer()
        trf.action_apply_default_taxes()
        trf.action_submit()
        trf.action_approve()
        # Completion proceeds to accounting; if accounts are missing it raises a
        # different (accounting) error, never the checklist gate.
        try:
            trf.action_complete()
        except UserError as exc:
            self.assertNotIn('required documents', str(exc).lower())

    def test_document_transfer_link(self):
        trf = self._transfer()
        doc = self.env['sa.property.document'].create({
            'document_type': 'transfer_deed',
            'property_id': self.property.id,
            'transfer_id': trf.id})
        trf.invalidate_recordset()
        self.assertEqual(trf.document_count, 1)
        self.assertEqual(doc.transfer_id, trf)


@tagged('post_install', '-at_install')
class TestAccessRoles(TransactionCase):
    """Phase 9: Sales Agent role hierarchy and record-rule scoping."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.agent_group = cls.env.ref(
            'sa_property_management.group_sa_property_agent')
        cls.user_group = cls.env.ref(
            'sa_property_management.group_sa_property_user')
        cls.manager_group = cls.env.ref(
            'sa_property_management.group_sa_property_manager')
        cls.project = cls.env['sa.property.project'].create({
            'name': 'ACL Society', 'code': 'ACL-SOC',
            'total_area': 50, 'area_uom': 'kanal'})
        cls.property = cls.env['sa.property'].create({
            'name': 'ACL Plot', 'project_id': cls.project.id,
            'property_type': 'plot', 'area': 5, 'area_uom': 'marla',
            'base_price': 5000000.0, 'state': 'available'})
        cls.plan = cls.env['sa.payment.plan'].create({
            'name': 'ACL Plan', 'down_payment_percent': 10.0,
            'installment_count': 4, 'frequency': 'monthly'})
        cls.customer = cls.env['res.partner'].create({'name': 'ACL Buyer'})
        # v19 renamed res.users.groups_id -> group_ids.
        group_field = 'group_ids' if 'group_ids' in cls.env['res.users']._fields \
            else 'groups_id'
        cls.agent = cls.env['res.users'].create({
            'name': 'Agent User', 'login': 'acl_agent_unit',
            group_field: [(6, 0, [cls.agent_group.id])]})

    def test_hierarchy(self):
        self.assertIn(self.agent_group, self.user_group.implied_ids)
        # v19 renamed res.groups.trans_implied_ids -> all_implied_ids.
        trans_field = 'all_implied_ids' \
            if 'all_implied_ids' in self.env['res.groups']._fields \
            else 'trans_implied_ids'
        self.assertIn(self.agent_group, self.manager_group[trans_field])

    def test_agent_is_not_user_or_manager(self):
        self.assertFalse(self.agent.has_group(
            'sa_property_management.group_sa_property_user'))
        self.assertFalse(self.agent.has_group(
            'sa_property_management.group_sa_property_manager'))

    def test_agent_reads_catalog(self):
        as_agent = self.env(user=self.agent)
        self.assertTrue(as_agent['sa.property'].search_count([]) >= 0)
        self.assertTrue(as_agent['sa.payment.plan'].search_count([]) >= 0)

    def test_agent_creates_own_booking(self):
        as_agent = self.env(user=self.agent)
        booking = as_agent['sa.property.booking'].create({
            'customer_id': self.customer.id,
            'property_id': self.property.id,
            'payment_plan_id': self.plan.id,
            'total_price': 5000000.0,
            'booking_date': date.today()})
        self.assertEqual(booking.salesperson_id, self.agent)

    def test_agent_cannot_write_payment_plan(self):
        as_agent = self.env(user=self.agent)
        with self.assertRaises(AccessError):
            as_agent['sa.payment.plan'].browse(self.plan.id).write(
                {'note': 'blocked'})
