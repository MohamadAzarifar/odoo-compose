# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaConstructionPhase(models.Model):
    _name = 'sa.construction.phase'
    _description = 'Construction Phase'
    _order = 'construction_id, sequence, id'

    construction_id = fields.Many2one(
        'sa.construction.project', string='Construction Project',
        required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Phase', required=True)
    weight = fields.Float(
        default=1.0,
        help="Relative weight used to compute the overall project progress.")
    progress = fields.Float(string='Progress')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], default='pending', required=True)
    date_start = fields.Date(string='Planned Start')
    date_end = fields.Date(string='Planned End')
    task_id = fields.Many2one(
        'project.task', string='Task', readonly=True, copy=False,
        help="Scheduling task created in the linked project.")
    company_id = fields.Many2one(
        related='construction_id.company_id', store=True)

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'done':
            self.progress = 100.0
        elif self.state == 'pending':
            self.progress = 0.0

    @api.constrains('progress')
    def _check_progress(self):
        for phase in self:
            if phase.progress < 0 or phase.progress > 100:
                raise ValidationError(
                    _("Phase progress must be between 0 and 100."))

    def _create_task(self):
        Task = self.env['project.task']
        for phase in self:
            project = phase.construction_id.project_id
            if phase.task_id or not project:
                continue
            phase.task_id = Task.create({
                'name': phase.name,
                'project_id': project.id,
                'date_deadline': phase.date_end,
            })
        return True

    def action_create_task(self):
        self.construction_id._ensure_project()
        return self._create_task()
