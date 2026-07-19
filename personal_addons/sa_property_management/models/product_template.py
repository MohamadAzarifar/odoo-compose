# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sa_property_id = fields.Many2one(
        'sa.property', string='Property Unit', copy=False, index=True,
        help="Property unit this product represents, if any.")
