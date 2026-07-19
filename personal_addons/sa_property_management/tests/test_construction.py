# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestConstructionBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Project = cls.env['sa.construction.project']
        cls.Contract = cls.env['sa.construction.contract']
        cls.Ipc = cls.env['sa.construction.ipc']
        cls.Req = cls.env['sa.construction.requisition']
        cls.Issue = cls.env['sa.construction.material.issue']
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Test Contractor', 'supplier_rank': 1})
        cls.material = cls.env['product.product'].create({
            'name': 'Test Cement', 'type': 'consu', 'is_storable': True,
            'standard_price': 500.0, 'list_price': 600.0})

    def _new_project(self, **vals):
        values = {'title': 'Test Build', 'budget_amount': 1000000.0,
                  'contractor_id': self.vendor.id}
        values.update(vals)
        return self.Project.create(values)

    def _confirmed_contract(self, project, qty=100.0, rate=1000.0, retention=10.0):
        contract = self.Contract.create({
            'title': 'Civil Works', 'construction_id': project.id,
            'contractor_id': self.vendor.id, 'retention_percent': retention})
        self.env['sa.construction.boq.line'].create({
            'contract_id': contract.id, 'product_id': self.material.id,
            'name': 'Concrete', 'quantity': qty, 'unit_rate': rate})
        contract.action_confirm()
        return contract


@tagged('post_install', '-at_install')
class TestConstructionProject(TestConstructionBase):

    def test_sequence_assigned(self):
        project = self._new_project()
        self.assertTrue(project.name.startswith('CON-'))

    def test_plan_creates_backend_resources(self):
        project = self._new_project()
        self.assertFalse(project.project_id)
        project.action_plan()
        self.assertEqual(project.state, 'planning')
        self.assertTrue(project.project_id)
        self.assertTrue(project.analytic_account_id)
        self.assertTrue(project.site_location_id)
        self.assertEqual(project.site_location_id.usage, 'internal')

    def test_weighted_progress(self):
        project = self._new_project()
        self.env['sa.construction.phase'].create({
            'construction_id': project.id, 'name': 'A',
            'weight': 1.0, 'progress': 50.0})
        self.env['sa.construction.phase'].create({
            'construction_id': project.id, 'name': 'B',
            'weight': 3.0, 'progress': 0.0})
        self.assertAlmostEqual(project.progress, 12.5, places=2)

    def test_done_forces_full_progress(self):
        project = self._new_project()
        self.env['sa.construction.phase'].create({
            'construction_id': project.id, 'name': 'A',
            'weight': 1.0, 'progress': 10.0})
        project.action_plan()
        project.action_start()
        project.action_done()
        self.assertEqual(project.state, 'done')
        self.assertEqual(project.progress, 100.0)
        self.assertTrue(project.date_end_actual)

    def test_generate_tasks(self):
        project = self._new_project()
        phase = self.env['sa.construction.phase'].create({
            'construction_id': project.id, 'name': 'Foundation', 'weight': 1.0})
        project.action_plan()
        project.action_generate_tasks()
        self.assertTrue(phase.task_id)
        self.assertEqual(phase.task_id.project_id, project.project_id)


@tagged('post_install', '-at_install')
class TestConstructionContract(TestConstructionBase):

    def test_contract_value(self):
        project = self._new_project()
        contract = self.Contract.create({
            'title': 'Works', 'construction_id': project.id,
            'contractor_id': self.vendor.id})
        self.env['sa.construction.boq.line'].create({
            'contract_id': contract.id, 'name': 'Item',
            'quantity': 10.0, 'unit_rate': 250.0})
        self.assertAlmostEqual(contract.contract_value, 2500.0, places=2)

    def test_confirm_requires_boq(self):
        project = self._new_project()
        contract = self.Contract.create({
            'title': 'Empty', 'construction_id': project.id,
            'contractor_id': self.vendor.id})
        with self.assertRaises(UserError):
            contract.action_confirm()


@tagged('post_install', '-at_install')
class TestConstructionIpc(TestConstructionBase):

    def test_ipc_amounts(self):
        project = self._new_project()
        contract = self._confirmed_contract(project)
        boq = contract.boq_line_ids
        ipc = self.Ipc.create({
            'contract_id': contract.id, 'retention_percent': 10.0})
        self.env['sa.construction.ipc.line'].create({
            'ipc_id': ipc.id, 'boq_line_id': boq.id,
            'name': 'Concrete', 'quantity': 40.0})
        self.assertAlmostEqual(ipc.amount_gross, 40000.0, places=2)
        self.assertAlmostEqual(ipc.retention_amount, 4000.0, places=2)
        self.assertAlmostEqual(ipc.amount_net, 36000.0, places=2)

    def test_approve_updates_boq_certified(self):
        project = self._new_project()
        contract = self._confirmed_contract(project)
        boq = contract.boq_line_ids
        ipc = self.Ipc.create({'contract_id': contract.id})
        self.env['sa.construction.ipc.line'].create({
            'ipc_id': ipc.id, 'boq_line_id': boq.id, 'quantity': 40.0})
        ipc.action_approve()
        self.assertEqual(ipc.state, 'approved')
        self.assertAlmostEqual(boq.qty_certified, 40.0, places=2)
        self.assertAlmostEqual(boq.qty_remaining, 60.0, places=2)

    def test_over_certification_blocked(self):
        project = self._new_project()
        contract = self._confirmed_contract(project, qty=100.0)
        boq = contract.boq_line_ids
        ipc = self.Ipc.create({'contract_id': contract.id})
        self.env['sa.construction.ipc.line'].create({
            'ipc_id': ipc.id, 'boq_line_id': boq.id, 'quantity': 150.0})
        with self.assertRaises(UserError):
            ipc.action_approve()

    def test_create_bill_clears_tax_and_keeps_rate(self):
        project = self._new_project()
        contract = self._confirmed_contract(project)
        boq = contract.boq_line_ids
        ipc = self.Ipc.create({'contract_id': contract.id})
        self.env['sa.construction.ipc.line'].create({
            'ipc_id': ipc.id, 'boq_line_id': boq.id, 'quantity': 40.0})
        ipc.action_approve()
        ipc.action_create_bill()
        bill = ipc.bill_id
        self.assertEqual(ipc.state, 'billed')
        self.assertEqual(bill.move_type, 'in_invoice')
        self.assertFalse(bill.line_ids.filtered(lambda l: l.tax_line_id))
        self.assertAlmostEqual(bill.amount_total, 40000.0, places=2)

    def test_bill_posts_cost_to_analytic(self):
        project = self._new_project()
        project.action_plan()
        contract = self._confirmed_contract(project)
        boq = contract.boq_line_ids
        ipc = self.Ipc.create({'contract_id': contract.id})
        self.env['sa.construction.ipc.line'].create({
            'ipc_id': ipc.id, 'boq_line_id': boq.id, 'quantity': 40.0})
        ipc.action_approve()
        ipc.action_create_bill()
        ipc.bill_id.action_post()
        self.assertAlmostEqual(project.cost_subcontract, 40000.0, places=2)
        self.assertAlmostEqual(project.actual_cost, 40000.0, places=2)
        self.assertAlmostEqual(project.cost_variance, 960000.0, places=2)


@tagged('post_install', '-at_install')
class TestConstructionProcurement(TestConstructionBase):

    def test_rfq_links_back_and_has_no_analytic(self):
        project = self._new_project()
        project.action_plan()
        req = self.Req.create({
            'construction_id': project.id, 'vendor_id': self.vendor.id})
        self.env['sa.construction.requisition.line'].create({
            'requisition_id': req.id, 'product_id': self.material.id,
            'name': 'Cement', 'quantity': 50.0, 'uom_id': self.material.uom_id.id})
        req.action_approve()
        req.action_create_rfq()
        self.assertEqual(req.state, 'purchased')
        self.assertEqual(req.po_count, 1)
        po = req.purchase_order_ids
        self.assertEqual(po.sa_requisition_id, req)
        # procurement must not book the construction analytic (avoids double count)
        self.assertFalse(po.order_line.analytic_distribution)

    def test_rfq_requires_vendor(self):
        project = self._new_project()
        req = self.Req.create({'construction_id': project.id})
        self.env['sa.construction.requisition.line'].create({
            'requisition_id': req.id, 'product_id': self.material.id,
            'quantity': 5.0})
        req.action_approve()
        with self.assertRaises(UserError):
            req.action_create_rfq()


@tagged('post_install', '-at_install')
class TestConstructionMaterialIssue(TestConstructionBase):

    def test_issue_creates_picking_and_cost(self):
        project = self._new_project()
        project.action_plan()
        issue = self.Issue.create({'construction_id': project.id})
        self.env['sa.construction.material.issue.line'].create({
            'issue_id': issue.id, 'product_id': self.material.id,
            'name': 'Cement', 'quantity': 30.0, 'uom_id': self.material.uom_id.id})
        self.assertAlmostEqual(issue.amount_total, 15000.0, places=2)
        issue.action_issue()
        self.assertEqual(issue.state, 'done')
        self.assertTrue(issue.picking_id)
        self.assertEqual(issue.picking_id.state, 'done')
        self.assertAlmostEqual(project.cost_material, 15000.0, places=2)


@tagged('post_install', '-at_install')
class TestConstructionCostModel(TestConstructionBase):

    def test_combined_actual_cost(self):
        project = self._new_project()
        project.action_plan()

        # subcontract -> IPC -> posted bill (40,000)
        contract = self._confirmed_contract(project)
        ipc = self.Ipc.create({'contract_id': contract.id})
        self.env['sa.construction.ipc.line'].create({
            'ipc_id': ipc.id, 'boq_line_id': contract.boq_line_ids.id,
            'quantity': 40.0})
        ipc.action_approve()
        ipc.action_create_bill()
        ipc.bill_id.action_post()

        # material issue (15,000)
        issue = self.Issue.create({'construction_id': project.id})
        self.env['sa.construction.material.issue.line'].create({
            'issue_id': issue.id, 'product_id': self.material.id,
            'quantity': 30.0, 'uom_id': self.material.uom_id.id})
        issue.action_issue()

        # labour timesheet (8,000)
        employee = self.env['hr.employee'].create({
            'name': 'Worker', 'company_id': project.company_id.id})
        line = self.env['account.analytic.line'].create({
            'name': 'Labour', 'account_id': project.analytic_account_id.id,
            'project_id': project.project_id.id, 'employee_id': employee.id,
            'unit_amount': 16.0})
        line.amount = -8000.0

        self.assertAlmostEqual(project.cost_subcontract, 40000.0, places=2)
        self.assertAlmostEqual(project.cost_material, 15000.0, places=2)
        self.assertAlmostEqual(project.cost_labour, 8000.0, places=2)
        self.assertAlmostEqual(project.actual_cost, 63000.0, places=2)
        self.assertAlmostEqual(project.cost_variance, 937000.0, places=2)
