# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class CrmLead(models.Model):
    """Extend the native CRM lead/opportunity with real-estate context so the
    standard pipeline, stages, activities and UTM source tracking can be used
    for property leads."""
    _inherit = 'crm.lead'

    sa_source_id = fields.Many2one(
        'sa.lead.source', string='Integration Source', index=True,
        help="The lead-source integration (Meta, Apollo, website, ...) that "
             "captured this lead.")
    sa_project_id = fields.Many2one(
        'sa.property.project', string='Interested Project')
    sa_property_id = fields.Many2one(
        'sa.property', string='Interested Unit',
        domain="[('project_id', '=', sa_project_id)]")
    sa_property_type = fields.Selection(
        [('plot', 'Plot'),
         ('house', 'House'),
         ('apartment', 'Apartment'),
         ('shop', 'Shop'),
         ('commercial', 'Commercial Unit'),
         ('office', 'Office')],
        string='Property Type')
    sa_purpose = fields.Selection(
        [('investment', 'Investment'),
         ('self_use', 'Self Use')],
        string='Buying Purpose')
    sa_budget_min = fields.Monetary(
        string='Budget From', currency_field='company_currency')
    sa_budget_max = fields.Monetary(
        string='Budget To', currency_field='company_currency')
    sa_area_preference = fields.Char(string='Preferred Size / Area')

    sa_booking_ids = fields.One2many(
        'sa.property.booking', 'crm_lead_id', string='Bookings')
    sa_booking_count = fields.Integer(
        compute='_compute_sa_booking_count', string='# Bookings')

    @api.depends('sa_booking_ids')
    def _compute_sa_booking_count(self):
        for lead in self:
            lead.sa_booking_count = len(lead.sa_booking_ids)

    @api.onchange('sa_project_id')
    def _onchange_sa_project_id(self):
        if self.sa_property_id and \
                self.sa_property_id.project_id != self.sa_project_id:
            self.sa_property_id = False

    def action_sa_create_booking(self):
        """Jump to a pre-filled draft booking for this lead."""
        self.ensure_one()
        ctx = {
            'default_customer_id': self.partner_id.id,
            'default_crm_lead_id': self.id,
        }
        if self.sa_project_id:
            ctx['default_project_id'] = self.sa_project_id.id
        if self.sa_property_id:
            ctx['default_property_id'] = self.sa_property_id.id
            if self.sa_property_id.base_price:
                ctx['default_total_price'] = self.sa_property_id.base_price
        elif self.expected_revenue:
            ctx['default_total_price'] = self.expected_revenue
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Booking'),
            'res_model': 'sa.property.booking',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }

    def action_sa_view_bookings(self):
        """Open the bookings created from this lead."""
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Bookings'),
            'res_model': 'sa.property.booking',
            'domain': [('crm_lead_id', '=', self.id)],
            'context': {
                'default_crm_lead_id': self.id,
                'default_customer_id': self.partner_id.id,
            },
        }
        if self.sa_booking_count == 1:
            action.update(view_mode='form', res_id=self.sa_booking_ids.id)
        else:
            action.update(view_mode='list,form')
        return action
