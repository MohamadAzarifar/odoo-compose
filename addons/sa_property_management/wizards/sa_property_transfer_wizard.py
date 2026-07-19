# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaPropertyTransferWizard(models.TransientModel):
    """Quick-start wizard to create a property transfer record."""
    _name = 'sa.property.transfer.wizard'
    _description = 'Initiate Property Transfer'

    property_id = fields.Many2one(
        'sa.property', required=True,
        domain=[('state', 'in', ('sold', 'booked', 'available'))])
    from_partner_id = fields.Many2one('res.partner', string='Current Owner', required=True)
    to_partner_id = fields.Many2one('res.partner', string='New Owner', required=True)
    transfer_date = fields.Date(
        required=True, default=fields.Date.context_today)
    sale_price = fields.Monetary(currency_field='currency_id', required=True)
    dc_value = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        prop_id = self.env.context.get('default_property_id') \
            or (self.env.context.get('active_model') == 'sa.property'
                and self.env.context.get('active_id'))
        if prop_id:
            prop = self.env['sa.property'].browse(prop_id)
            res.update({
                'property_id': prop.id,
                'from_partner_id': prop.current_owner_id.id,
                'sale_price': prop.base_price,
                'dc_value': prop.dc_value,
            })
        return res

    @api.onchange('property_id')
    def _onchange_property_id(self):
        if self.property_id:
            self.from_partner_id = self.property_id.current_owner_id
            self.sale_price = self.property_id.base_price
            self.dc_value = self.property_id.dc_value

    def action_create(self):
        self.ensure_one()
        if self.from_partner_id == self.to_partner_id:
            raise UserError(_("Seller and buyer must be different contacts."))
        transfer = self.env['sa.property.transfer'].create({
            'property_id': self.property_id.id,
            'from_partner_id': self.from_partner_id.id,
            'to_partner_id': self.to_partner_id.id,
            'transfer_date': self.transfer_date,
            'sale_price': self.sale_price,
            'dc_value': self.dc_value,
        })
        transfer.action_apply_default_taxes()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sa.property.transfer',
            'res_id': transfer.id,
            'view_mode': 'form',
        }
