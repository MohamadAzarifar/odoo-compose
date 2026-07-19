# -*- coding: utf-8 -*-
from odoo import fields, models


class SaPropertyImage(models.Model):
    """An additional photo in a property's or project's gallery."""
    _name = 'sa.property.image'
    _description = 'Property / Project Image'
    _inherit = ['sa.image.optimize.mixin']
    _order = 'sequence, id'

    _sa_image_fields = ('image',)

    name = fields.Char(string='Title')
    sequence = fields.Integer(default=10)
    image = fields.Image(string='Image', max_width=1920, max_height=1920,
                         required=True)
    property_id = fields.Many2one(
        'sa.property', string='Property', ondelete='cascade', index=True)
    project_id = fields.Many2one(
        'sa.property.project', string='Project', ondelete='cascade', index=True)


class SaMarketingCollateral(models.Model):
    """Marketing collateral attached to a project or property unit
    (brochure, floor plan, price list, video link, etc.)."""
    _name = 'sa.marketing.collateral'
    _description = 'Marketing Collateral'
    _order = 'sequence, id'

    name = fields.Char(string='Title', required=True)
    sequence = fields.Integer(default=10)
    collateral_type = fields.Selection(
        [('brochure', 'Brochure'),
         ('floor_plan', 'Floor Plan'),
         ('price_list', 'Price List'),
         ('site_plan', 'Site / Master Plan'),
         ('payment_plan', 'Payment Plan'),
         ('video', 'Video Link'),
         ('other', 'Other')],
        string='Type', default='brochure', required=True)
    file = fields.Binary(string='File', attachment=True)
    file_name = fields.Char(string='File Name')
    url = fields.Char(string='URL / Video Link',
                      help="External link, e.g. a YouTube walkthrough.")
    description = fields.Text()
    active = fields.Boolean(default=True)
    property_id = fields.Many2one(
        'sa.property', string='Property', ondelete='cascade', index=True)
    project_id = fields.Many2one(
        'sa.property.project', string='Project', ondelete='cascade', index=True)
