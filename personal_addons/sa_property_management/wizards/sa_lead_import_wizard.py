# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaLeadImportWizard(models.TransientModel):
    """Manual fallback to the webhook: paste leads, one per line, and create
    them in the CRM tagged to the chosen source."""
    _name = 'sa.lead.import.wizard'
    _description = 'Quick Import Leads'

    source_id = fields.Many2one(
        'sa.lead.source', string='Source', required=True)
    data = fields.Text(
        string='Leads',
        help="One lead per line as: Name, Email, Phone\n"
             "Email and phone are optional, e.g.:\n"
             "Ali Khan, ali@example.com, 0300-1234567\n"
             "Sara Malik, , 0321-7654321")
    created_count = fields.Integer(readonly=True)

    def action_import(self):
        self.ensure_one()
        if not self.data or not self.data.strip():
            raise UserError(_("Paste at least one lead line first."))
        count = 0
        for raw in self.data.splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(',')]
            payload = {
                'name': parts[0] if len(parts) > 0 else '',
                'email': parts[1] if len(parts) > 1 else '',
                'phone': parts[2] if len(parts) > 2 else '',
            }
            if not any(payload.values()):
                continue
            self.source_id._create_lead_from_payload(payload)
            count += 1
        if not count:
            raise UserError(_("No valid leads found in the pasted text."))
        self.created_count = count
        return self.source_id.action_view_leads()
