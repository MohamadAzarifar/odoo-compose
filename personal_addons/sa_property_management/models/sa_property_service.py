# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

RECURRENCE_MONTHS = {
    'monthly': 1,
    'quarterly': 3,
    'half_yearly': 6,
    'yearly': 12,
}


class SaPropertyService(models.Model):
    """Catalog of billable real-estate services: amenities, subscriptions,
    maintenance and utility (electricity) charges."""
    _name = 'sa.property.service'
    _description = 'Property Service / Charge'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)

    service_type = fields.Selection(
        [('amenity', 'Amenity'),
         ('subscription', 'Subscription'),
         ('maintenance', 'Maintenance'),
         ('electricity', 'Electricity'),
         ('water', 'Water / Gas'),
         ('security', 'Security'),
         ('other', 'Other')],
        string='Type', default='maintenance', required=True)

    product_id = fields.Many2one(
        'product.product', string='Invoice Product', required=True,
        domain="[('sale_ok', '=', True)]",
        help="Product used to build the customer invoice line.")
    default_price = fields.Monetary(
        string='Default Price', currency_field='currency_id')
    recurrence = fields.Selection(
        [('monthly', 'Monthly'),
         ('quarterly', 'Quarterly'),
         ('half_yearly', 'Half-Yearly'),
         ('yearly', 'Yearly'),
         ('one_time', 'One Time')],
        default='monthly', required=True)
    description = fields.Text()


class SaPropertyServiceAssignment(models.Model):
    """A service/charge assigned to a property and billed to a customer,
    optionally on a recurring cycle generated automatically by cron."""
    _name = 'sa.property.service.assignment'
    _description = 'Property Service Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'next_invoice_date, id'
    _rec_name = 'display_name'

    name = fields.Char(string='Reference', required=True, copy=False,
                       default=lambda self: _('New'), tracking=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id,
        help="Billing currency for the generated service invoices.")

    service_id = fields.Many2one(
        'sa.property.service', string='Service', required=True, tracking=True)
    service_type = fields.Selection(
        related='service_id.service_type', store=True, readonly=True)
    property_id = fields.Many2one(
        'sa.property', string='Property', required=True, tracking=True,
        ondelete='cascade', index=True)
    project_id = fields.Many2one(
        related='property_id.project_id', store=True, readonly=True)
    customer_id = fields.Many2one(
        'res.partner', string='Bill To', required=True, tracking=True)

    price = fields.Monetary(currency_field='currency_id', tracking=True)
    recurrence = fields.Selection(
        [('monthly', 'Monthly'),
         ('quarterly', 'Quarterly'),
         ('half_yearly', 'Half-Yearly'),
         ('yearly', 'Yearly'),
         ('one_time', 'One Time')],
        default='monthly', required=True, tracking=True)

    date_start = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(string='End Date', tracking=True,
                           help="Leave empty for open-ended recurring billing.")
    next_invoice_date = fields.Date(
        string='Next Invoice Date', tracking=True,
        help="The cron generates an invoice on or after this date.")
    last_invoice_date = fields.Date(readonly=True, copy=False)

    state = fields.Selection(
        [('running', 'Running'),
         ('expired', 'Expired'),
         ('stopped', 'Stopped')],
        default='running', required=True, tracking=True, copy=False)
    auto_post = fields.Boolean(
        string='Auto-Post Invoices', default=False,
        help="Post generated invoices automatically instead of leaving them in draft.")
    payment_term_id = fields.Many2one(
        'account.payment.term', string='Payment Terms',
        default=lambda self: self._default_payment_term(),
        help="Native Odoo payment terms applied to generated service invoices.")

    invoice_ids = fields.One2many(
        'account.move', 'sa_service_assignment_id', string='Invoices',
        copy=False)
    invoice_count = fields.Integer(compute='_compute_invoice_count', store=False)

    note = fields.Text()

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'Assignment reference must be unique per company.'),
        ('price_positive', 'CHECK(price >= 0)', 'Price cannot be negative.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.property.service.assignment') or _('New')
            if not vals.get('next_invoice_date'):
                vals['next_invoice_date'] = vals.get(
                    'date_start') or fields.Date.context_today(self)
        return super().create(vals_list)

    @api.depends('name', 'service_id.name', 'property_id.code')
    def _compute_display_name(self):
        for rec in self:
            parts = [p for p in (rec.service_id.name, rec.property_id.code) if p]
            rec.display_name = '%s (%s)' % (rec.name, ' / '.join(parts)) if parts else rec.name

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    @api.model
    def _default_payment_term(self):
        ICP = self.env['ir.config_parameter'].sudo()
        term_id = ICP.get_param('sa_property_management.default_payment_term_id')
        if term_id:
            term = self.env['account.payment.term'].browse(int(term_id)).exists()
            return term.id if term else False
        return False

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id:
            self.price = self.service_id.default_price
            self.recurrence = self.service_id.recurrence

    @api.onchange('property_id')
    def _onchange_property_id(self):
        if self.property_id and not self.customer_id:
            self.customer_id = self.property_id.current_owner_id
        if self.property_id and self.property_id.currency_id:
            self.currency_id = self.property_id.currency_id

    # --- Billing ---
    def _next_date(self, from_date):
        self.ensure_one()
        months = RECURRENCE_MONTHS.get(self.recurrence)
        if not months:
            return False
        return from_date + relativedelta(months=months)

    def _prepare_invoice_vals(self, invoice_date):
        self.ensure_one()
        product = self.service_id.product_id
        label = '%s - %s' % (self.service_id.name,
                             self.property_id.display_name or self.property_id.code or '')
        return {
            'move_type': 'out_invoice',
            'partner_id': self.customer_id.id,
            'invoice_date': invoice_date,
            'invoice_origin': self.name,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'invoice_payment_term_id': self.payment_term_id.id or False,
            'sa_service_assignment_id': self.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'name': label,
                'quantity': 1.0,
                'price_unit': self.price,
            })],
        }

    def _generate_invoice(self, invoice_date=None):
        self.ensure_one()
        invoice_date = invoice_date or fields.Date.context_today(self)
        move = self.env['account.move'].create(
            self._prepare_invoice_vals(invoice_date))
        if self.auto_post:
            move.action_post()
        self.last_invoice_date = invoice_date
        # advance schedule
        nxt = self._next_date(invoice_date)
        if not nxt or (self.date_end and nxt > self.date_end):
            self.state = 'expired'
            self.next_invoice_date = False
        else:
            self.next_invoice_date = nxt
        return move

    def action_generate_invoice(self):
        """Manually generate the next invoice now."""
        moves = self.env['account.move']
        for rec in self:
            if rec.state != 'running':
                raise UserError(_(
                    "Assignment %s is not running.") % rec.display_name)
            moves |= rec._generate_invoice()
        if len(moves) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'res_id': moves.id,
                'view_mode': 'form',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', moves.ids)],
        }

    def action_stop(self):
        self.write({'state': 'stopped', 'next_invoice_date': False})

    def action_resume(self):
        for rec in self:
            rec.state = 'running'
            if not rec.next_invoice_date:
                rec.next_invoice_date = fields.Date.context_today(self)

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': {'create': False},
        }

    @api.model
    def _cron_generate_service_bills(self):
        """Auto-generate invoices for all due recurring assignments."""
        today = fields.Date.context_today(self)
        due = self.search([
            ('state', '=', 'running'),
            ('next_invoice_date', '!=', False),
            ('next_invoice_date', '<=', today),
        ])
        for rec in due:
            # Guard against an end date already passed.
            if rec.date_end and rec.next_invoice_date > rec.date_end:
                rec.state = 'expired'
                rec.next_invoice_date = False
                continue
            rec._generate_invoice(rec.next_invoice_date)
        return True
