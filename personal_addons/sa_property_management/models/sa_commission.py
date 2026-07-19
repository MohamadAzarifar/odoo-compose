# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaCommission(models.Model):
    """Commission earned by a dealer or investor on a property booking.

    Each commission is paid through a standard Odoo vendor bill so it flows
    natively into Accounting (payables, payments, reporting).

        draft ─▶ confirmed ─▶ billed ─▶ paid
                      │
                      └─▶ cancelled
    """
    _name = 'sa.commission'
    _description = 'Property Commission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    state = fields.Selection(
        [('draft', 'Draft'),
         ('confirmed', 'Confirmed'),
         ('billed', 'Billed'),
         ('paid', 'Paid'),
         ('cancelled', 'Cancelled')],
        default='draft', required=True, tracking=True, copy=False)

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id)
    date = fields.Date(default=fields.Date.context_today, required=True,
                       tracking=True)

    beneficiary_type = fields.Selection(
        [('dealer', 'Dealer'),
         ('investor', 'Investor'),
         ('other', 'Other')],
        string='Beneficiary Type', default='dealer', required=True,
        tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Beneficiary', required=True, tracking=True,
        help="Contact paid for this commission (becomes a vendor).")
    dealer_id = fields.Many2one('sa.property.dealer', string='Dealer')

    booking_id = fields.Many2one(
        'sa.property.booking', string='Booking', ondelete='cascade',
        tracking=True)
    deal_id = fields.Many2one(
        'sa.property.deal', string='Investor Deal', ondelete='set null')
    property_id = fields.Many2one(
        related='booking_id.property_id', store=True, readonly=True)

    base_amount = fields.Monetary(
        currency_field='currency_id',
        help="Amount the commission percentage is applied to (usually the "
             "sale price).")
    commission_percent = fields.Float(string='Rate (%)', digits=(6, 3))
    commission_amount = fields.Monetary(
        currency_field='currency_id', compute='_compute_commission_amount',
        store=True, readonly=False, tracking=True)

    vendor_bill_id = fields.Many2one(
        'account.move', string='Vendor Bill', copy=False, readonly=True)
    bill_payment_state = fields.Selection(
        related='vendor_bill_id.payment_state', string='Bill Payment Status',
        readonly=True)
    bill_count = fields.Integer(compute='_compute_bill_count')

    note = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.commission') or _('New')
        return super().create(vals_list)

    @api.depends('base_amount', 'commission_percent')
    def _compute_commission_amount(self):
        for rec in self:
            if rec.commission_percent:
                rec.commission_amount = rec.base_amount * rec.commission_percent / 100.0
            else:
                # Preserve a manually entered amount when no percentage is set.
                rec.commission_amount = rec.commission_amount

    def _compute_bill_count(self):
        for rec in self:
            rec.bill_count = 1 if rec.vendor_bill_id else 0

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft commissions can be confirmed."))
            if rec.commission_amount <= 0:
                raise UserError(_(
                    "Commission amount must be greater than zero."))
            rec.state = 'confirmed'

    def action_create_vendor_bill(self):
        for rec in self:
            if rec.state not in ('confirmed',):
                raise UserError(_(
                    "Confirm the commission before billing it."))
            if rec.vendor_bill_id:
                raise UserError(_("A vendor bill already exists."))
            if rec.partner_id.supplier_rank < 1:
                rec.partner_id.supplier_rank = 1
            bill = self.env['account.move'].create(rec._prepare_vendor_bill_vals())
            rec.vendor_bill_id = bill.id
            rec.state = 'billed'
        return self.action_view_bill()

    def action_mark_paid(self):
        for rec in self:
            if rec.state != 'billed':
                raise UserError(_(
                    "Only billed commissions can be marked as paid."))
            rec.state = 'paid'

    def action_cancel(self):
        for rec in self:
            if rec.vendor_bill_id and rec.vendor_bill_id.state == 'posted':
                raise UserError(_(
                    "Cancel or reverse the posted vendor bill first."))
            rec.vendor_bill_id.filtered(
                lambda m: m.state == 'draft').unlink()
            rec.state = 'cancelled'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_(
                    "Only cancelled commissions can be reset to draft."))
            rec.state = 'draft'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_commission_expense_account(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        account_id = ICP.get_param(
            'sa_property_management.commission_expense_account_id')
        if account_id:
            account = self.env['account.account'].browse(
                int(account_id)).exists()
            if account:
                return account
        return self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_ids', 'in', self.company_id.id),
        ], limit=1)

    def _get_purchase_journal(self):
        self.ensure_one()
        return self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    def _prepare_vendor_bill_vals(self):
        self.ensure_one()
        account = self._get_commission_expense_account()
        journal = self._get_purchase_journal()
        if not journal:
            raise UserError(_("No purchase journal found for this company."))
        label = _('Commission %s - %s') % (
            self.name, self.property_id.display_name or '')
        return {
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.date,
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'sa_commission_id': self.id,
            'invoice_line_ids': [(0, 0, {
                'name': label,
                'quantity': 1.0,
                'price_unit': self.commission_amount,
                'account_id': account.id if account else False,
            })],
        }

    def action_view_bill(self):
        self.ensure_one()
        if not self.vendor_bill_id:
            raise UserError(_("No vendor bill yet."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bill'),
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.vendor_bill_id.id,
        }
