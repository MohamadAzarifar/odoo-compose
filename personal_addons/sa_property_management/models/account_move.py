# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    sa_service_assignment_id = fields.Many2one(
        'sa.property.service.assignment', string='Service Assignment',
        copy=False, index=True, ondelete='set null')
    sa_commission_id = fields.Many2one(
        'sa.commission', string='Property Commission',
        copy=False, index=True, ondelete='set null')
