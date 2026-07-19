# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaPropertyDeal(models.Model):
    """Bulk investor deal.

    An investor commits an advance and is allocated a set of property units.
    When any of those units is later sold to an end customer, the investor
    earns a configurable commission (in addition to the dealer commission).

        draft ─▶ active ─▶ closed
                    │
                    └─▶ cancelled
    """
    _name = 'sa.property.deal'
    _description = 'Investor Deal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deal_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    state = fields.Selection(
        [('draft', 'Draft'),
         ('active', 'Active'),
         ('closed', 'Closed'),
         ('cancelled', 'Cancelled')],
        default='draft', required=True, tracking=True, copy=False)

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        'res.currency', required=True,
        default=lambda self: self.env.company.currency_id)
    deal_date = fields.Date(default=fields.Date.context_today, required=True,
                            tracking=True)

    investor_id = fields.Many2one(
        'res.partner', string='Investor', required=True, tracking=True)
    salesperson_id = fields.Many2one(
        'res.users', string='Account Manager',
        default=lambda self: self.env.user)

    property_ids = fields.One2many(
        'sa.property', 'deal_id', string='Allocated Units')
    property_count = fields.Integer(compute='_compute_stats')
    sold_count = fields.Integer(compute='_compute_stats')

    advance_amount = fields.Monetary(
        currency_field='currency_id', tracking=True,
        help="Amount the investor commits / pre-pays for this deal.")
    advance_payment_id = fields.Many2one(
        'account.payment', string='Advance Payment', copy=False, readonly=True)

    commission_basis = fields.Selection(
        [('percent', 'Percentage of Sale'),
         ('fixed', 'Fixed per Unit')],
        string='Investor Earning Basis', default='percent', required=True)
    investor_commission_percent = fields.Float(
        string='Investor Rate (%)', digits=(6, 3), default=1.0)
    investor_commission_fixed = fields.Monetary(
        string='Fixed per Unit', currency_field='currency_id')

    commission_ids = fields.One2many(
        'sa.commission', 'deal_id', string='Investor Commissions')
    commission_count = fields.Integer(compute='_compute_stats')
    total_commission = fields.Monetary(
        currency_field='currency_id', compute='_compute_stats')

    note = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.property.deal') or _('New')
            if vals.get('investor_id'):
                self.env['res.partner'].browse(
                    vals['investor_id']).sa_is_property_investor = True
        return super().create(vals_list)

    @api.depends('property_ids', 'property_ids.state',
                 'commission_ids', 'commission_ids.commission_amount')
    def _compute_stats(self):
        for rec in self:
            rec.property_count = len(rec.property_ids)
            rec.sold_count = len(rec.property_ids.filtered(
                lambda p: p.state in ('booked', 'sold', 'transferred')))
            rec.commission_count = len(rec.commission_ids)
            rec.total_commission = sum(rec.commission_ids.mapped(
                'commission_amount'))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft deals can be activated."))
            if not rec.investor_id:
                raise UserError(_("Set the investor first."))
            rec.state = 'active'

    def action_close(self):
        for rec in self:
            if rec.state != 'active':
                raise UserError(_("Only active deals can be closed."))
            rec.state = 'closed'

    def action_cancel(self):
        for rec in self:
            if rec.advance_payment_id and rec.advance_payment_id.state == 'posted':
                raise UserError(_(
                    "Reverse the posted advance payment before cancelling."))
            rec.state = 'cancelled'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_("Only cancelled deals can reset to draft."))
            rec.state = 'draft'

    # ------------------------------------------------------------------
    # Advance payment
    # ------------------------------------------------------------------
    def action_register_advance(self):
        self.ensure_one()
        if self.advance_payment_id:
            return self._open_advance_payment()
        if self.advance_amount <= 0:
            raise UserError(_("Set an advance amount greater than zero first."))
        journal = self.env['account.journal'].search([
            ('type', 'in', ('bank', 'cash')),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            raise UserError(_("No bank or cash journal found."))
        if self.investor_id.customer_rank < 1:
            self.investor_id.customer_rank = 1
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.investor_id.id,
            'amount': self.advance_amount,
            'currency_id': self.currency_id.id,
            'journal_id': journal.id,
            'date': self.deal_date,
            'memo': _('Investor advance - %s') % self.name,
        })
        payment.action_post()
        self.advance_payment_id = payment.id
        return self._open_advance_payment()

    def _open_advance_payment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Advance Payment'),
            'res_model': 'account.payment',
            'view_mode': 'form',
            'res_id': self.advance_payment_id.id,
        }

    # ------------------------------------------------------------------
    # Commission for a sold unit
    # ------------------------------------------------------------------
    def _prepare_investor_commission_vals(self, booking):
        self.ensure_one()
        if self.commission_basis == 'fixed':
            percent = 0.0
            amount = self.investor_commission_fixed
        else:
            percent = self.investor_commission_percent
            amount = booking.total_price * percent / 100.0
        return {
            'beneficiary_type': 'investor',
            'partner_id': self.investor_id.id,
            'deal_id': self.id,
            'booking_id': booking.id,
            'base_amount': booking.total_price,
            'commission_percent': percent,
            'commission_amount': amount,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
        }

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def action_view_properties(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Allocated Units'),
            'res_model': 'sa.property',
            'view_mode': 'list,form',
            'domain': [('deal_id', '=', self.id)],
            'context': {'default_deal_id': self.id},
        }

    def action_view_commissions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Investor Commissions'),
            'res_model': 'sa.commission',
            'view_mode': 'list,form',
            'domain': [('deal_id', '=', self.id)],
        }
