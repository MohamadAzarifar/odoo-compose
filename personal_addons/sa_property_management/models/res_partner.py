# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'sa.qr.mixin']

    _sa_doc_type = _('Customer File')

    # --- Identity ---
    sa_cnic = fields.Char(string='National ID',
                          help="Government-issued national identity number "
                               "(e.g. CNIC, SSN, Aadhaar, Emirates ID).")
    sa_ntn = fields.Char(string='Tax Number',
                         help="Taxpayer identification number (e.g. NTN, TIN, VAT).")
    sa_passport_no = fields.Char(string='Passport No.')
    sa_father_husband_name = fields.Char(
        string='Father / Husband Name',
        help="Guardian name as printed on the national ID, where applicable.")
    sa_dob = fields.Date(string='Birth Date')
    sa_gender = fields.Selection(
        [('male', 'Male'),
         ('female', 'Female'),
         ('other', 'Other')],
        string='Sex')
    sa_nationality = fields.Char(string='Nationality')
    sa_occupation = fields.Char(string='Occupation')

    sa_is_property_customer = fields.Boolean(string='Property Customer')
    sa_is_property_dealer = fields.Boolean(string='Is Property Dealer')
    sa_is_property_investor = fields.Boolean(string='Is Property Investor')
    sa_dealer_id = fields.Many2one(
        'sa.property.dealer', string='Dealer Record',
        compute='_compute_sa_dealer_id', store=False)

    # --- Next of Kin ---
    sa_nok_name = fields.Char(string='Next of Kin Name')
    sa_nok_relation = fields.Selection(
        [('father', 'Father'),
         ('mother', 'Mother'),
         ('spouse', 'Spouse'),
         ('son', 'Son'),
         ('daughter', 'Daughter'),
         ('brother', 'Brother'),
         ('sister', 'Sister'),
         ('other', 'Other')],
        string='Relationship')
    sa_nok_cnic = fields.Char(string='Next of Kin CNIC')
    sa_nok_mobile = fields.Char(string='Next of Kin Mobile')
    sa_nok_phone = fields.Char(string='Next of Kin Telephone')
    sa_nok_address = fields.Text(string='Next of Kin Address')

    # --- Biometric verification ---
    sa_biometric_verification_ids = fields.One2many(
        'sa.biometric.verification', 'customer_id',
        string='Biometric Verifications')
    sa_biometric_verified = fields.Boolean(
        string='Identity Verified', compute='_compute_sa_biometric',
        search='_search_sa_biometric_verified',
        help="Set when the customer has at least one verified biometric "
             "record.")
    sa_biometric_verification_count = fields.Integer(
        string='Verifications', compute='_compute_sa_biometric')

    def _compute_sa_biometric(self):
        Verification = self.env['sa.biometric.verification']
        verified_groups = Verification._read_group(
            [('customer_id', 'in', self.ids), ('state', '=', 'verified')],
            ['customer_id'], ['__count'])
        verified_map = {p.id: c for p, c in verified_groups}
        all_groups = Verification._read_group(
            [('customer_id', 'in', self.ids)],
            ['customer_id'], ['__count'])
        all_map = {p.id: c for p, c in all_groups}
        for rec in self:
            rec.sa_biometric_verified = bool(verified_map.get(rec.id))
            rec.sa_biometric_verification_count = all_map.get(rec.id, 0)

    def _search_sa_biometric_verified(self, operator, value):
        verified = self.env['sa.biometric.verification'].search(
            [('state', '=', 'verified')]).customer_id.ids
        positive = (operator == '=' and value) or (operator == '!=' and not value)
        return [('id', 'in' if positive else 'not in', verified)]

    def action_view_biometric_verifications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Biometric Verifications'),
            'res_model': 'sa.biometric.verification',
            'view_mode': 'list,form',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id},
        }

    def _compute_sa_dealer_id(self):
        Dealer = self.env['sa.property.dealer']
        for rec in self:
            rec.sa_dealer_id = Dealer.search(
                [('partner_id', '=', rec.id)], limit=1)

    def _sa_status_info(self):
        self.ensure_one()
        return {
            'doc_type': self._sa_doc_type,
            'reference': self.name or '',
            'status': 'verified',
            'status_label': _('Verified'),
            'valid': True,
            'rows': [
                (_('CNIC'), self.sa_cnic or _('—')),
                (_('Father / Husband'), self.sa_father_husband_name or _('—')),
                (_('Mobile'), self.mobile or self.phone or _('—')),
                (_('City'), self.city or _('—')),
            ],
        }
