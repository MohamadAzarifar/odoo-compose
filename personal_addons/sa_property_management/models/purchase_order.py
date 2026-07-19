# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sa_requisition_id = fields.Many2one(
        'sa.construction.requisition', string='Material Requisition',
        copy=False, index=True,
        help="Construction material requisition that originated this order.")
    sa_construction_id = fields.Many2one(
        'sa.construction.project', string='Construction Project',
        related='sa_requisition_id.construction_id', store=True)
