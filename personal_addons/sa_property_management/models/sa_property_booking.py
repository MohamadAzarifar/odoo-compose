# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaPropertyBooking(models.Model):
    """Booking / Sale agreement between a customer and a property.

    Lifecycle:
        draft  ───▶  confirmed  ───▶  in_payment  ───▶  completed
                                                 │
                                                 └─▶  cancelled
    """
    _name = 'sa.property.booking'
    _description = 'Property Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'sa.qr.mixin']
    _order = 'booking_date desc, id desc'

    _sa_doc_type = _('Property Booking')

    name = fields.Char(string='Booking Reference', required=True, copy=False,
                       default=lambda self: _('New'), tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'),
         ('confirmed', 'Confirmed'),
         ('in_payment', 'In Payment'),
         ('completed', 'Completed'),
         ('cancelled', 'Cancelled')],
        default='draft', required=True, tracking=True, copy=False)

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id,
        help="Transaction currency. Defaults from the property/project and "
             "flows to the generated customer invoices.")

    customer_id = fields.Many2one(
        'res.partner', required=True, tracking=True)
    customer_biometric_verified = fields.Boolean(
        related='customer_id.sa_biometric_verified', readonly=True,
        string='Customer Identity Verified')
    project_id = fields.Many2one(
        'sa.property.project', string='Project', tracking=True,
        help="Select the project first, then pick an available property "
             "within it.")
    property_id = fields.Many2one(
        'sa.property', required=True, tracking=True, ondelete='restrict',
        domain="[('state', '=', 'available'), ('project_id', '=', project_id)]")
    dealer_id = fields.Many2one(
        'sa.property.dealer', string='Dealer', tracking=True)
    salesperson_id = fields.Many2one(
        'res.users', string='Salesperson',
        default=lambda self: self.env.user, tracking=True)
    crm_lead_id = fields.Many2one(
        'crm.lead', string='Source Opportunity', ondelete='set null',
        index=True, copy=False, tracking=True,
        help="The CRM lead/opportunity this booking originated from. "
             "Confirming the booking marks the opportunity won.")

    booking_date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True)
    total_price = fields.Monetary(
        currency_field='currency_id', required=True, tracking=True,
        help="Agreed sale price. Defaults to the property base price.")
    payment_plan_id = fields.Many2one(
        'sa.payment.plan', string='Payment Plan', required=True, tracking=True)
    payment_term_id = fields.Many2one(
        'account.payment.term', string='Payment Terms',
        default=lambda self: self._default_payment_term(),
        help="Native Odoo payment terms applied to invoices generated for "
             "this booking's installments.")

    installment_ids = fields.One2many(
        'sa.property.installment', 'booking_id', string='Installments',
        copy=False)
    invoice_ids = fields.One2many(
        'account.move', 'sa_booking_id', string='Invoices',
        domain=[('move_type', 'in', ('out_invoice', 'out_refund'))])
    sale_order_id = fields.Many2one(
        'sale.order', string='Sale Order', copy=False, readonly=True,
        tracking=True,
        help="Native sale order generated on confirmation. Drives the "
             "standard Sales and Inventory (delivery) flow. Invoicing is "
             "handled through the installment schedule.")
    commission_ids = fields.One2many(
        'sa.commission', 'booking_id', string='Commissions', copy=False)
    document_ids = fields.One2many(
        'sa.property.document', 'booking_id', string='Documents', copy=False)

    installment_count = fields.Integer(compute='_compute_aggregates', store=False)
    invoice_count = fields.Integer(compute='_compute_aggregates', store=False)
    commission_count = fields.Integer(compute='_compute_aggregates', store=False)
    document_count = fields.Integer(compute='_compute_aggregates', store=False)
    amount_invoiced = fields.Monetary(
        currency_field='currency_id', compute='_compute_aggregates', store=False)
    amount_paid = fields.Monetary(
        currency_field='currency_id', compute='_compute_aggregates', store=False)
    amount_residual = fields.Monetary(
        currency_field='currency_id', compute='_compute_aggregates', store=False)

    commission_amount = fields.Monetary(
        currency_field='currency_id', compute='_compute_commission', store=True)

    note = fields.Text()

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'Booking reference must be unique per company.'),
        ('total_price_positive', 'CHECK(total_price > 0)',
         'Total price must be greater than zero.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.property.booking') or _('New')
            # Keep project in sync with the property for records created
            # programmatically (wizards, imports) where onchange doesn't run.
            if vals.get('property_id') and not vals.get('project_id'):
                prop = self.env['sa.property'].browse(vals['property_id'])
                if prop.project_id:
                    vals['project_id'] = prop.project_id.id
        return super().create(vals_list)

    def _sa_status_info(self):
        self.ensure_one()
        labels = dict(self._fields['state'].selection)
        return {
            'doc_type': self._sa_doc_type,
            'reference': self.name,
            'status': self.state,
            'status_label': labels.get(self.state, self.state),
            'valid': self.state not in ('cancelled',),
            'rows': [
                (_('Customer'), self.customer_id.name or ''),
                (_('Property'), self.property_id.display_name or ''),
                (_('Project'), self.project_id.name or ''),
                (_('Booking Date'), str(self.booking_date or '')),
                (_('Sale Price'), '%s %s' % (
                    self.currency_id.symbol or '',
                    '{:,.0f}'.format(self.total_price or 0.0))),
            ],
        }

    @api.model
    def _default_payment_term(self):
        ICP = self.env['ir.config_parameter'].sudo()
        term_id = ICP.get_param('sa_property_management.default_payment_term_id')
        if term_id:
            term = self.env['account.payment.term'].browse(int(term_id)).exists()
            return term.id if term else False
        return False

    @api.onchange('project_id')
    def _onchange_project_id(self):
        # When the project changes, drop any property that no longer belongs
        # to it so the user always picks an available unit under the project.
        if self.property_id and self.property_id.project_id != self.project_id:
            self.property_id = False

    @api.onchange('property_id')
    def _onchange_property_id(self):
        if self.property_id:
            # Keep the project in sync with the chosen property.
            if self.property_id.project_id:
                self.project_id = self.property_id.project_id
            # Always reflect the selected property's own price so switching
            # units updates the figure instead of keeping a stale value.
            self.total_price = self.property_id.base_price
            if self.property_id.currency_id:
                self.currency_id = self.property_id.currency_id

    @api.depends('installment_ids', 'invoice_ids', 'commission_ids',
                 'document_ids',
                 'invoice_ids.amount_total', 'invoice_ids.amount_residual',
                 'invoice_ids.state')
    def _compute_aggregates(self):
        for rec in self:
            posted = rec.invoice_ids.filtered(lambda m: m.state == 'posted')
            rec.installment_count = len(rec.installment_ids)
            rec.invoice_count = len(rec.invoice_ids)
            rec.commission_count = len(rec.commission_ids)
            rec.document_count = len(rec.document_ids)
            rec.amount_invoiced = sum(posted.mapped('amount_total'))
            rec.amount_residual = sum(posted.mapped('amount_residual'))
            rec.amount_paid = rec.amount_invoiced - rec.amount_residual

    @api.depends('total_price', 'dealer_id.commission_percent')
    def _compute_commission(self):
        for rec in self:
            rec.commission_amount = rec.total_price * (
                rec.dealer_id.commission_percent or 0.0) / 100.0

    @api.constrains('property_id', 'state')
    def _check_property_availability(self):
        for rec in self:
            if rec.state in ('confirmed', 'in_payment', 'completed'):
                # No other active booking on this property
                other = self.search([
                    ('id', '!=', rec.id),
                    ('property_id', '=', rec.property_id.id),
                    ('state', 'in', ('confirmed', 'in_payment', 'completed')),
                ], limit=1)
                if other:
                    raise ValidationError(_(
                        "Property '%s' already has active booking '%s'."
                    ) % (rec.property_id.display_name, other.name))

    # ----- Workflow -----

    def _check_biometric_verification(self):
        self.ensure_one()
        require = self.env['ir.config_parameter'].sudo().get_param(
            'sa_property_management.require_biometric_verification')
        if require and require not in ('False', '0', '') \
                and not self.customer_biometric_verified:
            raise UserError(_(
                "Customer '%s' must complete biometric identity verification "
                "before this booking can be confirmed. Use the 'Verify "
                "Identity' button to capture it."
            ) % (self.customer_id.display_name or ''))

    def action_verify_customer_identity(self):
        self.ensure_one()
        if not self.customer_id:
            raise UserError(_("Select a customer first."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Verify Customer Identity'),
            'res_model': 'sa.biometric.verification',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_customer_id': self.customer_id.id,
                'default_booking_id': self.id,
            },
        }

    def action_confirm(self):
        """Mark the booking confirmed; generate the installment schedule and
        the down-payment invoice."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft bookings can be confirmed."))
            if not rec.payment_plan_id:
                raise UserError(_("Select a payment plan first."))
            rec._check_biometric_verification()
            if rec.property_id.state in ('sold', 'transferred', 'blocked'):
                raise UserError(_(
                    "Property '%s' is not bookable (state: %s)."
                ) % (rec.property_id.display_name, rec.property_id.state))

            rec._generate_installments()
            rec.state = 'confirmed'
            rec.property_id.state = 'booked'
            rec.property_id.current_owner_id = rec.customer_id
            rec._create_sale_order()
            rec._create_invoice_for_first_due()
            rec._generate_commissions()
            rec._update_crm_on_confirm()
            rec.state = 'in_payment'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'completed':
                raise UserError(_("Completed bookings cannot be cancelled."))
            # Cancel related draft invoices; refuse if any are posted
            posted = rec.invoice_ids.filtered(lambda m: m.state == 'posted')
            if posted:
                raise UserError(_(
                    "Cannot cancel: %s invoice(s) already posted. Refund them "
                    "individually first."
                ) % len(posted))
            rec.invoice_ids.filtered(lambda m: m.state == 'draft').unlink()
            rec.installment_ids.unlink()
            if rec.sale_order_id and rec.sale_order_id.state != 'cancel':
                rec.sale_order_id._action_cancel()
            if rec.property_id.state == 'booked':
                rec.property_id.state = 'available'
                rec.property_id.current_owner_id = False
            rec.state = 'cancelled'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_("Only cancelled bookings can reset to draft."))
            rec.state = 'draft'

    def _cancel_for_surrender(self):
        """Cancel a booking as part of a unit surrender.

        Unlike :meth:`action_cancel`, this is allowed even when posted
        invoices exist because the surrender wizard handles any refund
        separately. Draft invoices and the installment schedule are removed
        and the linked sale order is cancelled.
        """
        for rec in self:
            if rec.state == 'cancelled':
                continue
            rec.invoice_ids.filtered(lambda m: m.state == 'draft').unlink()
            rec.installment_ids.unlink()
            if rec.sale_order_id and rec.sale_order_id.state != 'cancel':
                rec.sale_order_id._action_cancel()
            rec.state = 'cancelled'

    def action_mark_completed(self):
        for rec in self:
            if rec.state != 'in_payment':
                raise UserError(_(
                    "Booking must be in payment to be marked completed."))
            unpaid = rec.installment_ids.filtered(
                lambda i: i.state not in ('paid', 'cancelled'))
            if unpaid:
                raise UserError(_(
                    "%s installment(s) are still unpaid.") % len(unpaid))
            rec.state = 'completed'
            rec.property_id.state = 'sold'
            rec._validate_delivery()

    # ----- Helpers -----

    def _generate_installments(self):
        Installment = self.env['sa.property.installment']
        for rec in self:
            rec.installment_ids.unlink()
            schedule = rec.payment_plan_id.generate_schedule(
                rec.total_price, rec.booking_date)
            for entry in schedule:
                Installment.create({
                    'booking_id': rec.id,
                    'sequence': entry['sequence'],
                    'name': entry['name'],
                    'due_date': entry['due_date'],
                    'amount': entry['amount'],
                    'line_type': entry['line_type'],
                })

    def _prepare_sale_order_vals(self):
        self.ensure_one()
        return {
            'partner_id': self.customer_id.id,
            'date_order': fields.Datetime.now(),
            'origin': self.name,
            'company_id': self.company_id.id,
            'user_id': self.salesperson_id.id or self.env.user.id,
            'payment_term_id': self.payment_term_id.id or False,
            'sa_booking_id': self.id,
        }

    def _prepare_sale_order_line_vals(self, order):
        self.ensure_one()
        product = self.property_id.product_id
        return {
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': 1.0,
            'price_unit': self.total_price,
            'name': self.property_id.display_name or product.display_name,
        }

    def _create_sale_order(self):
        """Create and confirm a native sale order for the booked unit.

        The sale order drives the standard Sales/Inventory flow (order +
        delivery). Customer invoicing remains driven by the installment
        schedule, so the order itself is not invoiced from here.
        """
        self.ensure_one()
        if self.sale_order_id:
            return self.sale_order_id
        if not self.property_id.product_id:
            self.property_id._sync_product()
        order = self.env['sale.order'].create(self._prepare_sale_order_vals())
        self.env['sale.order.line'].create(
            self._prepare_sale_order_line_vals(order))
        order.action_confirm()
        self.sale_order_id = order.id
        return order

    def _validate_delivery(self):
        """Validate outgoing deliveries so inventory reflects the sold unit."""
        self.ensure_one()
        if not self.sale_order_id:
            return
        pickings = self.sale_order_id.picking_ids.filtered(
            lambda p: p.state not in ('done', 'cancel'))
        for picking in pickings:
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            res = picking.button_validate()
            if isinstance(res, dict) \
                    and res.get('res_model') == 'stock.backorder.confirmation':
                self.env['stock.backorder.confirmation'].with_context(
                    res.get('context', {})).create({
                        'pick_ids': [(6, 0, picking.ids)],
                    }).process()

    def _generate_commissions(self):
        """Create dealer and investor commission lines on confirmation."""
        Commission = self.env['sa.commission']
        for rec in self:
            # Dealer commission
            if rec.dealer_id and rec.dealer_id.partner_id:
                already = rec.commission_ids.filtered(
                    lambda c: c.beneficiary_type == 'dealer'
                    and c.state != 'cancelled')
                if not already:
                    Commission.create({
                        'beneficiary_type': 'dealer',
                        'partner_id': rec.dealer_id.partner_id.id,
                        'dealer_id': rec.dealer_id.id,
                        'booking_id': rec.id,
                        'base_amount': rec.total_price,
                        'commission_percent': rec.dealer_id.commission_percent,
                        'currency_id': rec.currency_id.id,
                        'company_id': rec.company_id.id,
                    })
            # Investor commission when the unit belongs to an active deal
            deal = rec.property_id.deal_id
            if deal and deal.state == 'active' and deal.investor_id:
                already = rec.commission_ids.filtered(
                    lambda c: c.beneficiary_type == 'investor'
                    and c.state != 'cancelled')
                if not already:
                    Commission.create(
                        deal._prepare_investor_commission_vals(rec))

    def _get_property_income_account(self):
        """Return the income account to use on generated invoices."""
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        account_id = ICP.get_param('sa_property_management.default_income_account_id')
        if account_id:
            account = self.env['account.account'].browse(int(account_id)).exists()
            if account:
                return account
        # Fallback to the default sales income account
        return self.env['account.account'].search([
            ('account_type', '=', 'income'),
            ('company_ids', 'in', self.company_id.id),
        ], limit=1)

    def _get_sale_journal(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        journal_id = ICP.get_param('sa_property_management.property_journal_id')
        if journal_id:
            journal = self.env['account.journal'].browse(int(journal_id)).exists()
            if journal:
                return journal
        return self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    def _create_invoice_for_first_due(self):
        """Issue an invoice for the first unpaid installment."""
        for rec in self:
            first = rec.installment_ids.filtered(
                lambda i: not i.invoice_id
                and i.state in ('pending', 'overdue')).sorted('sequence')[:1]
            if first:
                first.action_generate_invoice()

    def action_view_invoices(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
        }
        if len(self.invoice_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': self.invoice_ids.id,
            })
        return action

    def action_view_installments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Installments'),
            'res_model': 'sa.property.installment',
            'view_mode': 'list,form',
            'domain': [('booking_id', '=', self.id)],
        }

    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError(_("No sale order linked to this booking yet."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_order_id.id,
        }

    def action_view_commissions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Commissions'),
            'res_model': 'sa.commission',
            'view_mode': 'list,form',
            'domain': [('booking_id', '=', self.id)],
            'context': {
                'default_booking_id': self.id,
                'default_base_amount': self.total_price,
            },
        }

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'sa.property.document',
            'view_mode': 'list,form',
            'domain': [('booking_id', '=', self.id)],
            'context': {
                'default_booking_id': self.id,
                'default_property_id': self.property_id.id,
                'default_partner_id': self.customer_id.id,
            },
        }

    def _update_crm_on_confirm(self):
        """Mark the originating opportunity won and set its revenue.

        Bookings created straight from a lead carry ``crm_lead_id``. On
        confirmation the pipeline should reflect the closed sale: a lead is
        promoted to an opportunity and any open opportunity is won.
        """
        self.ensure_one()
        lead = self.crm_lead_id
        if not lead:
            return
        if not lead.partner_id and self.customer_id:
            lead.partner_id = self.customer_id
        lead.expected_revenue = self.total_price
        if lead.type == 'lead':
            lead.convert_opportunity(self.customer_id or self.env['res.partner'])
        if lead.probability < 100 and lead.active:
            lead.action_set_won()
        lead.message_post(body=_(
            "Won via booking %s.") % self.name)

    def action_view_crm_lead(self):
        self.ensure_one()
        if not self.crm_lead_id:
            raise UserError(_("No source opportunity linked to this booking."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Source Opportunity'),
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'res_id': self.crm_lead_id.id,
        }

    def action_print_payment_schedule(self):
        self.ensure_one()
        return self.env.ref(
            'sa_property_management.action_report_sa_payment_schedule').report_action(self)
