# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaInstallmentPaymentWizard(models.TransientModel):
    """Batch payment registration for several installments at once."""
    _name = 'sa.installment.payment.wizard'
    _description = 'Register Installment Payments'

    installment_ids = fields.Many2many(
        'sa.property.installment', required=True,
        domain=[('state', 'in', ('pending', 'invoiced', 'overdue', 'partial'))])
    payment_date = fields.Date(
        required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one(
        'account.journal', string='Payment Journal', required=True,
        domain="[('type', 'in', ('bank', 'cash'))]")
    communication = fields.Char(string='Memo')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ids = self.env.context.get('active_ids')
        if ids and self.env.context.get('active_model') == 'sa.property.installment':
            res['installment_ids'] = [(6, 0, ids)]
        default_journal = self.env['account.journal'].search(
            [('type', 'in', ('bank', 'cash')),
             ('company_id', '=', self.env.company.id)],
            limit=1)
        if default_journal:
            res.setdefault('journal_id', default_journal.id)
        return res

    def action_register(self):
        self.ensure_one()
        if not self.installment_ids:
            raise UserError(_("No installments selected."))
        for inst in self.installment_ids:
            if not inst.invoice_id:
                inst.action_generate_invoice()
            if inst.invoice_id.state == 'draft':
                inst.invoice_id.action_post()
            payment_register = self.env['account.payment.register'].with_context(
                active_model='account.move',
                active_ids=inst.invoice_id.ids,
            ).create({
                'payment_date': self.payment_date,
                'journal_id': self.journal_id.id,
                'communication': self.communication or inst.display_name,
            })
            payment_register.action_create_payments()
        return {'type': 'ir.actions.act_window_close'}
