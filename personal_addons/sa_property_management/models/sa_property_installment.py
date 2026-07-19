# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaPropertyInstallment(models.Model):
    """One installment due against a booking."""
    _name = 'sa.property.installment'
    _description = 'Property Installment'
    _inherit = ['mail.thread', 'sa.qr.mixin']
    _order = 'booking_id, sequence, due_date'
    _rec_name = 'display_name'

    _sa_doc_type = _('Payment Receipt')

    booking_id = fields.Many2one(
        'sa.property.booking', required=True, ondelete='cascade', index=True)
    property_id = fields.Many2one(
        related='booking_id.property_id', store=True, readonly=True)
    customer_id = fields.Many2one(
        related='booking_id.customer_id', store=True, readonly=True)
    company_id = fields.Many2one(
        related='booking_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='booking_id.currency_id', store=True, readonly=True)

    sequence = fields.Integer(required=True, default=10)
    name = fields.Char(required=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)
    line_type = fields.Selection(
        [('down_payment', 'Down Payment'),
         ('installment', 'Installment'),
         ('extra', 'Balloon / Extra'),
         ('on_possession', 'On Possession')],
        default='installment', required=True)

    due_date = fields.Date(required=True, tracking=True)
    amount = fields.Monetary(currency_field='currency_id', required=True)

    invoice_id = fields.Many2one(
        'account.move', string='Invoice', copy=False, ondelete='set null')
    invoice_state = fields.Selection(
        related='invoice_id.state', store=False, readonly=True)
    amount_paid = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_payment', store=True)
    amount_residual = fields.Monetary(
        currency_field='currency_id',
        compute='_compute_payment', store=True)

    state = fields.Selection(
        [('pending', 'Pending'),
         ('invoiced', 'Invoiced'),
         ('partial', 'Partially Paid'),
         ('paid', 'Paid'),
         ('overdue', 'Overdue'),
         ('cancelled', 'Cancelled')],
        default='pending', required=True, tracking=True,
        compute='_compute_state', store=True)
    days_overdue = fields.Integer(compute='_compute_state', store=True)

    penalty_amount = fields.Monetary(
        currency_field='currency_id', compute='_compute_penalty', store=True,
        help="Accrued late-payment penalty based on the booking's payment "
             "plan policy and the number of days overdue.")
    penalty_invoice_id = fields.Many2one(
        'account.move', string='Penalty Invoice', copy=False,
        ondelete='set null',
        help="Separate customer invoice raised for the accrued penalty.")
    penalty_billed = fields.Boolean(
        compute='_compute_penalty_billed', store=True)

    @api.depends('name', 'booking_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s / %s' % (rec.booking_id.name or '', rec.name or '')

    def _sa_status_info(self):
        self.ensure_one()
        labels = dict(self._fields['state'].selection)
        sym = self.currency_id.symbol or ''
        return {
            'doc_type': self._sa_doc_type,
            'reference': self.display_name,
            'status': self.state,
            'status_label': labels.get(self.state, self.state),
            'valid': self.state == 'paid',
            'rows': [
                (_('Customer'), self.customer_id.name or ''),
                (_('Property'), self.property_id.display_name or ''),
                (_('Due Date'), str(self.due_date or '')),
                (_('Amount'), '%s %s' % (sym, '{:,.0f}'.format(self.amount or 0.0))),
                (_('Paid'), '%s %s' % (sym, '{:,.0f}'.format(self.amount_paid or 0.0))),
                (_('Outstanding'), '%s %s' % (sym, '{:,.0f}'.format(self.amount_residual or 0.0))),
            ],
        }

    @api.depends('invoice_id', 'invoice_id.amount_total',
                 'invoice_id.amount_residual', 'invoice_id.state', 'amount')
    def _compute_payment(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state == 'posted':
                rec.amount_paid = rec.invoice_id.amount_total - rec.invoice_id.amount_residual
                rec.amount_residual = rec.invoice_id.amount_residual
            else:
                rec.amount_paid = 0.0
                rec.amount_residual = rec.amount

    @api.depends('invoice_id', 'invoice_id.state', 'invoice_id.payment_state',
                 'amount_residual', 'due_date')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.state == 'cancelled':
                rec.days_overdue = 0
                continue
            rec.days_overdue = 0
            if not rec.invoice_id:
                if rec.due_date and rec.due_date < today:
                    rec.state = 'overdue'
                    rec.days_overdue = (today - rec.due_date).days
                else:
                    rec.state = 'pending'
                continue
            if rec.invoice_id.state in ('draft', 'cancel'):
                rec.state = 'invoiced' if rec.invoice_id.state == 'draft' else 'cancelled'
                continue
            # posted
            currency = rec.currency_id or rec.company_id.currency_id
            paid = rec.amount_paid
            residual = rec.amount_residual
            if currency.is_zero(residual):
                rec.state = 'paid'
            elif paid > 0 and not currency.is_zero(paid):
                if rec.due_date and rec.due_date < today:
                    rec.state = 'overdue'
                    rec.days_overdue = (today - rec.due_date).days
                else:
                    rec.state = 'partial'
            else:
                if rec.due_date and rec.due_date < today:
                    rec.state = 'overdue'
                    rec.days_overdue = (today - rec.due_date).days
                else:
                    rec.state = 'invoiced'

    @api.depends('state', 'days_overdue', 'amount_residual',
                 'booking_id.payment_plan_id.penalty_type',
                 'booking_id.payment_plan_id.penalty_value',
                 'booking_id.payment_plan_id.penalty_grace_days',
                 'booking_id.payment_plan_id.penalty_kibor_spread',
                 'booking_id.payment_plan_id.penalty_kibor_tenor')
    def _compute_penalty(self):
        today = fields.Date.context_today(self)
        for rec in self:
            plan = rec.booking_id.payment_plan_id
            if rec.state != 'overdue' or not plan \
                    or plan.penalty_type == 'none':
                rec.penalty_amount = 0.0
                continue
            rec.penalty_amount = plan.compute_penalty(
                rec.amount_residual, rec.days_overdue, ref_date=today)

    @api.depends('penalty_invoice_id', 'penalty_invoice_id.state')
    def _compute_penalty_billed(self):
        for rec in self:
            rec.penalty_billed = bool(
                rec.penalty_invoice_id
                and rec.penalty_invoice_id.state != 'cancel')

    # ----- Actions -----

    def action_bill_penalty(self):
        """Raise (or open) a customer invoice for the accrued penalty."""
        self.ensure_one()
        if self.penalty_invoice_id and self.penalty_invoice_id.state != 'cancel':
            return self._open_penalty_invoice()
        if self.penalty_amount <= 0:
            raise UserError(_("There is no accrued penalty to bill."))
        booking = self.booking_id
        journal = booking._get_sale_journal()
        if not journal:
            raise UserError(_(
                "No sales journal available for company %s.")
                % booking.company_id.name)
        account = self._get_penalty_income_account()
        if not account:
            raise UserError(_(
                "No income account available for the penalty. Configure a "
                "penalty income account in Property Management → Settings."))
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': booking.customer_id.id,
            'invoice_date': fields.Date.context_today(self),
            'journal_id': journal.id,
            'currency_id': self.currency_id.id,
            'company_id': booking.company_id.id,
            'sa_booking_id': booking.id,
            'sa_installment_id': self.id,
            'invoice_line_ids': [(0, 0, {
                'name': _('Late penalty - %s [%s]',
                          self.name, booking.name),
                'quantity': 1.0,
                'price_unit': self.penalty_amount,
                'account_id': account.id,
                'tax_ids': [(5, 0, 0)],
            })],
        })
        self.penalty_invoice_id = move.id
        return self._open_penalty_invoice()

    def _open_penalty_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Penalty Invoice'),
            'res_model': 'account.move',
            'res_id': self.penalty_invoice_id.id,
            'view_mode': 'form',
        }

    def _get_penalty_income_account(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        account_id = ICP.get_param(
            'sa_property_management.penalty_income_account_id')
        if account_id:
            account = self.env['account.account'].browse(
                int(account_id)).exists()
            if account:
                return account
        # Fall back to the booking's configured property income account
        return self.booking_id._get_property_income_account()

    def action_generate_invoice(self):
        """Create a customer invoice for this installment."""
        AccountMove = self.env['account.move']
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state != 'cancel':
                continue
            if rec.state == 'cancelled':
                continue
            booking = rec.booking_id
            account = booking._get_property_income_account()
            if not account:
                raise UserError(_(
                    "No income account configured. Configure one in "
                    "Property Management → Settings."))
            journal = booking._get_sale_journal()
            if not journal:
                raise UserError(_(
                    "No sales journal available for company %s.")
                    % booking.company_id.name)
            move = AccountMove.create({
                'move_type': 'out_invoice',
                'partner_id': booking.customer_id.id,
                'invoice_date': fields.Date.context_today(rec),
                'invoice_date_due': rec.due_date,
                'journal_id': journal.id,
                'currency_id': rec.currency_id.id,
                'company_id': booking.company_id.id,
                'invoice_payment_term_id': booking.payment_term_id.id or False,
                'invoice_origin': booking.sale_order_id.name or booking.name,
                'sa_booking_id': booking.id,
                'sa_installment_id': rec.id,
                'invoice_line_ids': [(0, 0, {
                    'name': _('%s - %s [%s]',
                        booking.property_id.display_name,
                        rec.name,
                        booking.name,
                    ),
                    'quantity': 1.0,
                    'price_unit': rec.amount,
                    'account_id': account.id,
                })],
            })
            rec.invoice_id = move.id

    def action_open_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No invoice yet — generate one first."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
        }

    def action_register_payment(self):
        """Open the standard account payment wizard for this installment."""
        self.ensure_one()
        if not self.invoice_id or self.invoice_id.state != 'posted':
            # Auto-generate + post so the wizard can run
            if not self.invoice_id:
                self.action_generate_invoice()
            if self.invoice_id.state == 'draft':
                self.invoice_id.action_post()
        return self.invoice_id.action_register_payment()

    def action_cancel(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.state == 'posted':
                raise UserError(_(
                    "Cannot cancel an installment with a posted invoice. "
                    "Cancel/refund the invoice first."))
            if rec.invoice_id and rec.invoice_id.state == 'draft':
                rec.invoice_id.button_cancel()
            rec.state = 'cancelled'

    # ----- Cron -----

    @api.model
    def _cron_update_overdue(self):
        """Daily cron to refresh overdue state and accrued penalties."""
        records = self.search([
            ('state', 'in', ('pending', 'invoiced', 'partial', 'overdue'))])
        records._compute_state()
        records._compute_penalty()


class AccountMove(models.Model):
    _inherit = 'account.move'

    sa_booking_id = fields.Many2one(
        'sa.property.booking', string='Property Booking', index=True,
        copy=False, ondelete='set null')
    sa_installment_id = fields.Many2one(
        'sa.property.installment', string='Property Installment', index=True,
        copy=False, ondelete='set null')
    sa_transfer_id = fields.Many2one(
        'sa.property.transfer', string='Property Transfer', index=True,
        copy=False, ondelete='set null')
