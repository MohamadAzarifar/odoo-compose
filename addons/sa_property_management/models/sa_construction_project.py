# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

CONSTRUCTION_STATES = [
    ('draft', 'Draft'),
    ('planning', 'Planning'),
    ('in_progress', 'In Progress'),
    ('on_hold', 'On Hold'),
    ('done', 'Completed'),
    ('cancelled', 'Cancelled'),
]


class SaConstructionProject(models.Model):
    _name = 'sa.construction.project'
    _description = 'Construction Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New'), tracking=True)
    title = fields.Char(string='Title', required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', store=True)

    property_project_id = fields.Many2one(
        'sa.property.project', string='Property Project', tracking=True,
        help="Real-estate project this construction effort belongs to.")
    property_id = fields.Many2one(
        'sa.property', string='Property', tracking=True,
        domain="['|', ('project_id', '=', property_project_id), ('project_id', '=', False)]",
        help="Specific unit/plot under construction, if applicable.")
    manager_id = fields.Many2one(
        'res.users', string='Project Manager', tracking=True,
        default=lambda self: self.env.user)
    contractor_id = fields.Many2one(
        'res.partner', string='Main Contractor', tracking=True)

    date_start = fields.Date(string='Start Date', tracking=True)
    date_end_planned = fields.Date(string='Planned Completion', tracking=True)
    date_end_actual = fields.Date(
        string='Actual Completion', readonly=True, copy=False, tracking=True)

    project_id = fields.Many2one(
        'project.project', string='Task Project', readonly=True, copy=False,
        help="Linked Odoo project holding the work-breakdown tasks and timesheets.")
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Cost Ledger', readonly=True, copy=False,
        help="Analytic account collecting every construction cost "
             "(subcontract certificates, issued materials and labour).")
    site_location_id = fields.Many2one(
        'stock.location', string='Site Location', readonly=True, copy=False,
        help="Internal stock location that represents this construction site.")

    description = fields.Html(string='Scope of Work')

    state = fields.Selection(
        CONSTRUCTION_STATES, default='draft', required=True, tracking=True,
        group_expand='_group_expand_state')

    budget_amount = fields.Monetary(string='Budget', tracking=True)
    actual_cost = fields.Monetary(
        string='Actual Cost', compute='_compute_costs')
    committed_cost = fields.Monetary(
        string='Committed Cost', compute='_compute_costs',
        help="Value certified on subcontracts that is not necessarily booked yet.")
    cost_variance = fields.Monetary(
        string='Budget Variance', compute='_compute_costs',
        help="Budget minus actual cost. Negative means over budget.")
    cost_subcontract = fields.Monetary(
        string='Subcontract Cost', compute='_compute_costs')
    cost_material = fields.Monetary(
        string='Material Cost', compute='_compute_costs')
    cost_labour = fields.Monetary(
        string='Labour Cost', compute='_compute_costs')

    progress = fields.Float(
        string='Progress', compute='_compute_progress', store=True,
        help="Weighted completion across all phases.")

    phase_ids = fields.One2many(
        'sa.construction.phase', 'construction_id', string='Phases')
    contract_ids = fields.One2many(
        'sa.construction.contract', 'construction_id', string='Subcontracts')
    requisition_ids = fields.One2many(
        'sa.construction.requisition', 'construction_id', string='Requisitions')
    issue_ids = fields.One2many(
        'sa.construction.material.issue', 'construction_id', string='Material Issues')

    phase_count = fields.Integer(compute='_compute_counts')
    contract_count = fields.Integer(compute='_compute_counts')
    requisition_count = fields.Integer(compute='_compute_counts')
    issue_count = fields.Integer(compute='_compute_counts')
    task_count = fields.Integer(compute='_compute_counts')

    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)',
         'The construction project reference must be unique per company.'),
    ]

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.model
    def _group_expand_state(self, states, domain, *args):
        return [key for key, _label in CONSTRUCTION_STATES]

    @api.depends('analytic_account_id', 'budget_amount',
                 'contract_ids.amount_certified')
    def _compute_costs(self):
        AAL = self.env['account.analytic.line']
        for rec in self:
            subcontract = material = labour = 0.0
            if rec.analytic_account_id:
                lines = AAL.search(
                    [('account_id', '=', rec.analytic_account_id.id)])
                for line in lines:
                    cost = -line.amount  # costs are stored as negative amounts
                    if line.move_line_id:
                        # booked from a vendor bill (IPC certificate)
                        subcontract += cost
                    elif line.project_id:
                        # labour recorded through timesheets
                        labour += cost
                    else:
                        # material issued to the site
                        material += cost
            rec.cost_subcontract = subcontract
            rec.cost_material = material
            rec.cost_labour = labour
            rec.actual_cost = subcontract + material + labour
            rec.committed_cost = sum(rec.contract_ids.mapped('amount_certified'))
            rec.cost_variance = rec.budget_amount - rec.actual_cost

    @api.depends('phase_ids.progress', 'phase_ids.weight', 'state')
    def _compute_progress(self):
        for rec in self:
            if rec.state == 'done':
                rec.progress = 100.0
                continue
            total_weight = sum(rec.phase_ids.mapped('weight'))
            if total_weight:
                rec.progress = sum(
                    p.weight * p.progress for p in rec.phase_ids) / total_weight
            else:
                rec.progress = 0.0

    def _compute_counts(self):
        task_data = {}
        if self.ids:
            projects = self.filtered('project_id')
            if projects:
                grouped = self.env['project.task']._read_group(
                    [('project_id', 'in', projects.mapped('project_id').ids)],
                    ['project_id'], ['__count'])
                task_data = {p.id: c for p, c in grouped}
        for rec in self:
            rec.phase_count = len(rec.phase_ids)
            rec.contract_count = len(rec.contract_ids)
            rec.requisition_count = len(rec.requisition_ids)
            rec.issue_count = len(rec.issue_ids)
            rec.task_count = task_data.get(rec.project_id.id, 0)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.construction.project') or _('New')
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Backend resources
    # ------------------------------------------------------------------
    def _ensure_project(self):
        self.ensure_one()
        if not self.project_id:
            self.project_id = self.env['project.project'].sudo().create({
                'name': self.title or self.name,
                'company_id': self.company_id.id,
                'allow_timesheets': True,
            })
        return self.project_id

    def _ensure_analytic_account(self):
        self.ensure_one()
        if self.analytic_account_id:
            return self.analytic_account_id
        project = self._ensure_project()
        account = project.account_id
        if not account:
            plan = self.env.ref(
                'analytic.analytic_plan_projects', raise_if_not_found=False) \
                or self.env['account.analytic.plan'].sudo().search([], limit=1)
            if not plan:
                raise UserError(_(
                    "No analytic plan is configured. Please create one under "
                    "Accounting before starting construction projects."))
            account = self.env['account.analytic.account'].sudo().create({
                'name': self.title or self.name,
                'plan_id': plan.id,
                'company_id': self.company_id.id,
            })
            project.sudo().account_id = account
        self.analytic_account_id = account.id
        return account

    def _ensure_site_location(self):
        self.ensure_one()
        if self.site_location_id:
            return self.site_location_id
        warehouse = self.env['stock.warehouse'].sudo().search(
            [('company_id', '=', self.company_id.id)], limit=1)
        parent = warehouse.lot_stock_id if warehouse else self.env[
            'stock.location'].sudo().search([('usage', '=', 'internal')], limit=1)
        if warehouse and warehouse.int_type_id and not warehouse.int_type_id.active:
            warehouse.int_type_id.sudo().active = True
        self.site_location_id = self.env['stock.location'].sudo().create({
            'name': self.name,
            'usage': 'internal',
            'location_id': parent.id if parent else False,
            'company_id': self.company_id.id,
        }).id
        return self.site_location_id

    def _prepare_backend_resources(self):
        for rec in self:
            rec._ensure_project()
            rec._ensure_analytic_account()
            rec._ensure_site_location()

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def action_plan(self):
        for rec in self:
            if rec.state not in ('draft', 'on_hold'):
                continue
            rec._prepare_backend_resources()
            rec.state = 'planning'

    def action_start(self):
        for rec in self:
            rec._prepare_backend_resources()
            if not rec.date_start:
                rec.date_start = fields.Date.context_today(rec)
            rec.state = 'in_progress'

    def action_hold(self):
        self.write({'state': 'on_hold'})

    def action_resume(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        for rec in self:
            rec.state = 'done'
            rec.date_end_actual = fields.Date.context_today(rec)
            rec.phase_ids.filtered(lambda p: p.state != 'done').write({
                'state': 'done', 'progress': 100.0,
            })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_generate_tasks(self):
        for rec in self:
            rec._ensure_project()
            rec.phase_ids.filtered(lambda p: not p.task_id)._create_task()

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def action_view_tasks(self):
        self.ensure_one()
        self._ensure_project()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tasks'),
            'res_model': 'project.task',
            'view_mode': 'list,form,kanban',
            'domain': [('project_id', '=', self.project_id.id)],
            'context': {'default_project_id': self.project_id.id},
        }

    def action_view_timesheets(self):
        self.ensure_one()
        self._ensure_project()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Timesheets'),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.project_id.id)],
            'context': {'default_project_id': self.project_id.id},
        }

    def action_view_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Subcontracts'),
            'res_model': 'sa.construction.contract',
            'view_mode': 'list,form',
            'domain': [('construction_id', '=', self.id)],
            'context': {'default_construction_id': self.id},
        }

    def action_view_requisitions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Requisitions'),
            'res_model': 'sa.construction.requisition',
            'view_mode': 'list,form',
            'domain': [('construction_id', '=', self.id)],
            'context': {'default_construction_id': self.id},
        }

    def action_view_issues(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Issues'),
            'res_model': 'sa.construction.material.issue',
            'view_mode': 'list,form',
            'domain': [('construction_id', '=', self.id)],
            'context': {'default_construction_id': self.id},
        }

    def action_open_analytic(self):
        self.ensure_one()
        self._ensure_analytic_account()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cost Ledger'),
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form',
            'domain': [('account_id', '=', self.analytic_account_id.id)],
        }
