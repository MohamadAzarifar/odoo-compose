# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaPropertyTransfer(models.Model):
    """Ownership transfer of a property between two parties.

    Lifecycle:
        draft → in_review → approved → completed
                                    └→ cancelled
    """
    _name = 'sa.property.transfer'
    _description = 'Property Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'transfer_date desc, id desc'

    name = fields.Char(
        required=True, copy=False, default=lambda self: _('New'),
        tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'),
         ('in_review', 'In Review'),
         ('approved', 'Approved'),
         ('completed', 'Completed'),
         ('cancelled', 'Cancelled')],
        default='draft', required=True, tracking=True, copy=False)

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)

    property_id = fields.Many2one(
        'sa.property', required=True, tracking=True, ondelete='restrict')
    project_id = fields.Many2one(
        related='property_id.project_id', store=True, readonly=True)
    from_partner_id = fields.Many2one(
        'res.partner', string='Current Owner', required=True, tracking=True)
    to_partner_id = fields.Many2one(
        'res.partner', string='New Owner', required=True, tracking=True)
    to_partner_biometric_verified = fields.Boolean(
        related='to_partner_id.sa_biometric_verified', readonly=True,
        string='New Owner Identity Verified')
    dealer_id = fields.Many2one('sa.property.dealer', tracking=True)

    transfer_date = fields.Date(
        required=True, default=fields.Date.context_today, tracking=True)
    sale_price = fields.Monetary(
        currency_field='currency_id', required=True, tracking=True)
    dc_value = fields.Monetary(
        currency_field='currency_id',
        help="DC notified value, used as base for FBR-type taxes.")

    tax_line_ids = fields.One2many(
        'sa.transfer.tax.line', 'transfer_id', string='Taxes', copy=True)
    misc_line_ids = fields.One2many(
        'sa.transfer.misc.line', 'transfer_id', string='Misc Charges', copy=True)

    amount_tax_buyer = fields.Monetary(
        currency_field='currency_id', compute='_compute_totals', store=True)
    amount_tax_seller = fields.Monetary(
        currency_field='currency_id', compute='_compute_totals', store=True)
    amount_misc_buyer = fields.Monetary(
        currency_field='currency_id', compute='_compute_totals', store=True)
    amount_misc_seller = fields.Monetary(
        currency_field='currency_id', compute='_compute_totals', store=True)
    total_buyer = fields.Monetary(
        currency_field='currency_id', compute='_compute_totals', store=True,
        help="Sale price + buyer taxes + buyer misc charges.")
    total_seller_deductions = fields.Monetary(
        currency_field='currency_id', compute='_compute_totals', store=True,
        help="Taxes & misc charges payable by the seller.")
    net_to_seller = fields.Monetary(
        currency_field='currency_id', compute='_compute_totals', store=True)

    move_id = fields.Many2one(
        'account.move', string='Accounting Entry', readonly=True, copy=False)
    move_state = fields.Selection(
        related='move_id.state', readonly=True)

    checklist_ids = fields.One2many(
        'sa.property.transfer.checklist', 'transfer_id',
        string='Documentation Checklist', copy=True)
    document_ids = fields.One2many(
        'sa.property.document', 'transfer_id', string='Documents', copy=False)
    document_count = fields.Integer(
        compute='_compute_documentation', store=False)
    checklist_total = fields.Integer(
        compute='_compute_documentation', store=False)
    checklist_done = fields.Integer(
        compute='_compute_documentation', store=False)
    checklist_progress = fields.Float(
        string='Checklist Progress', compute='_compute_documentation',
        store=False, help="Share of checklist items received (0-100).")
    checklist_complete = fields.Boolean(
        compute='_compute_documentation', store=False,
        help="True when every required checklist item has been received.")

    note = fields.Text()

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'Transfer reference must be unique per company.'),
        ('sale_price_positive', 'CHECK(sale_price > 0)',
         'Sale price must be greater than zero.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'sa.property.transfer') or _('New')
        return super().create(vals_list)

    @api.onchange('property_id')
    def _onchange_property_id(self):
        if self.property_id:
            self.from_partner_id = self.property_id.current_owner_id
            if not self.sale_price:
                self.sale_price = self.property_id.base_price
            if not self.dc_value:
                self.dc_value = self.property_id.dc_value

    @api.constrains('from_partner_id', 'to_partner_id')
    def _check_distinct_parties(self):
        for rec in self:
            if rec.from_partner_id == rec.to_partner_id:
                raise ValidationError(_(
                    "Seller and buyer must be different contacts."))

    @api.depends('tax_line_ids.amount', 'tax_line_ids.payer',
                 'misc_line_ids.amount', 'misc_line_ids.payer',
                 'sale_price')
    def _compute_totals(self):
        for rec in self:
            tax_buyer = 0.0
            tax_seller = 0.0
            for line in rec.tax_line_ids:
                if line.payer == 'buyer':
                    tax_buyer += line.amount
                elif line.payer == 'seller':
                    tax_seller += line.amount
                else:  # shared
                    tax_buyer += line.amount / 2.0
                    tax_seller += line.amount / 2.0
            misc_buyer = 0.0
            misc_seller = 0.0
            for line in rec.misc_line_ids:
                if line.payer == 'buyer':
                    misc_buyer += line.amount
                elif line.payer == 'seller':
                    misc_seller += line.amount
                else:
                    misc_buyer += line.amount / 2.0
                    misc_seller += line.amount / 2.0
            rec.amount_tax_buyer = tax_buyer
            rec.amount_tax_seller = tax_seller
            rec.amount_misc_buyer = misc_buyer
            rec.amount_misc_seller = misc_seller
            rec.total_buyer = (rec.sale_price or 0.0) + tax_buyer + misc_buyer
            rec.total_seller_deductions = tax_seller + misc_seller
            rec.net_to_seller = (rec.sale_price or 0.0) - tax_seller - misc_seller

    @api.depends('document_ids', 'checklist_ids',
                 'checklist_ids.is_done', 'checklist_ids.required')
    def _compute_documentation(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)
            total = len(rec.checklist_ids)
            done = len(rec.checklist_ids.filtered('is_done'))
            required_pending = rec.checklist_ids.filtered(
                lambda l: l.required and not l.is_done)
            rec.checklist_total = total
            rec.checklist_done = done
            rec.checklist_progress = (done / total * 100.0) if total else 0.0
            rec.checklist_complete = not required_pending

    # ----- Actions -----

    def action_apply_default_taxes(self):
        """Populate tax/misc lines from active configuration matching the property."""
        Tax = self.env['sa.transfer.tax']
        Misc = self.env['sa.misc.charge']
        TaxLine = self.env['sa.transfer.tax.line']
        MiscLine = self.env['sa.transfer.misc.line']
        for rec in self:
            rec.tax_line_ids.unlink()
            rec.misc_line_ids.unlink()
            country = (rec.company_id.sa_operating_country_id
                       or rec.company_id.country_id)
            country_domain = [('country_id', '=', False)]
            if country:
                country_domain = ['|', ('country_id', '=', False),
                                  ('country_id', '=', country.id)]
            taxes = Tax.search([
                ('active', '=', True),
                ('company_id', '=', rec.company_id.id),
                '|',
                ('property_type_filter', '=', 'all'),
                ('property_type_filter', '=', rec.property_id.property_type),
            ] + country_domain)
            for tax in taxes:
                TaxLine.create({
                    'transfer_id': rec.id,
                    'tax_id': tax.id,
                    'payer': tax.payer,
                    'amount': tax.compute_tax(rec.sale_price, rec.dc_value),
                })
            misc = Misc.search([
                ('active', '=', True),
                ('company_id', '=', rec.company_id.id),
                ('apply_on', 'in', ('transfer', 'both')),
            ] + country_domain)
            for charge in misc:
                MiscLine.create({
                    'transfer_id': rec.id,
                    'charge_id': charge.id,
                    'payer': charge.payer,
                    'amount': charge.compute_charge(rec.sale_price,
                                                   rec.property_id.area),
                })

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("Only draft transfers can be submitted."))
            if not rec.tax_line_ids and not rec.misc_line_ids:
                rec.action_apply_default_taxes()
            rec.state = 'in_review'

    def action_approve(self):
        for rec in self:
            if rec.state != 'in_review':
                raise UserError(_("Only transfers in review can be approved."))
            rec.state = 'approved'

    def _check_biometric_verification(self):
        self.ensure_one()
        require = self.env['ir.config_parameter'].sudo().get_param(
            'sa_property_management.require_biometric_verification')
        if require and require not in ('False', '0', '') \
                and not self.to_partner_biometric_verified:
            raise UserError(_(
                "New owner '%s' must complete biometric identity verification "
                "before this transfer can be completed. Use the 'Verify "
                "Identity' button to capture it."
            ) % (self.to_partner_id.display_name or ''))

    def action_verify_buyer_identity(self):
        self.ensure_one()
        if not self.to_partner_id:
            raise UserError(_("Select the new owner first."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Verify Buyer Identity'),
            'res_model': 'sa.biometric.verification',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_customer_id': self.to_partner_id.id,
                'default_transfer_id': self.id,
            },
        }

    def action_complete(self):
        """Finalize transfer: post the accounting entry, switch ownership."""
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_("Only approved transfers can be completed."))
            rec._check_biometric_verification()
            if rec.checklist_ids and not rec.checklist_complete:
                pending = rec.checklist_ids.filtered(
                    lambda l: l.required and not l.is_done)
                raise UserError(_(
                    "Cannot complete transfer '%(name)s': the following "
                    "required documents are still pending:\n%(items)s",
                    name=rec.name,
                    items='\n'.join('- %s' % l.name for l in pending)))
            rec._create_accounting_entry()
            rec.property_id.write({
                'current_owner_id': rec.to_partner_id.id,
                'state': 'transferred',
            })
            rec.state = 'completed'

    def action_cancel(self):
        for rec in self:
            if rec.move_id and rec.move_id.state == 'posted':
                raise UserError(_(
                    "Accounting entry is already posted. Reverse it manually "
                    "before cancelling the transfer."))
            if rec.move_id and rec.move_id.state == 'draft':
                rec.move_id.button_cancel()
            rec.state = 'cancelled'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != 'cancelled':
                raise UserError(_("Only cancelled transfers can reset to draft."))
            rec.state = 'draft'

    def _get_transfer_journal(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        journal_id = ICP.get_param('sa_property_management.transfer_journal_id')
        if journal_id:
            journal = self.env['account.journal'].browse(int(journal_id)).exists()
            if journal:
                return journal
        return self.env['account.journal'].search([
            ('type', 'in', ('sale', 'general')),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    def _create_accounting_entry(self):
        """Create a single journal entry recording the transfer:
        - debit buyer receivable for total_buyer
        - credit seller payable for net_to_seller
        - credit each tax account for its amount
        - credit each misc charge account for its amount
        """
        AccountMove = self.env['account.move']
        for rec in self:
            journal = rec._get_transfer_journal()
            if not journal:
                raise UserError(_(
                    "Configure a Property Transfer Journal in Settings."))
            # Use buyer's receivable / seller's payable from partner properties
            buyer_rcv = rec.to_partner_id.with_company(
                rec.company_id).property_account_receivable_id
            seller_pay = rec.from_partner_id.with_company(
                rec.company_id).property_account_payable_id
            if not buyer_rcv or not seller_pay:
                raise UserError(_(
                    "Buyer must have a receivable account and seller must have "
                    "a payable account configured."))

            lines = [
                (0, 0, {
                    'name': _('Buyer settlement - %s', rec.name),
                    'partner_id': rec.to_partner_id.id,
                    'account_id': buyer_rcv.id,
                    'debit': rec.total_buyer,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'name': _('Seller net proceeds - %s', rec.name),
                    'partner_id': rec.from_partner_id.id,
                    'account_id': seller_pay.id,
                    'debit': 0.0,
                    'credit': rec.net_to_seller,
                }),
            ]
            # Aggregate tax/misc credits per account
            credits = {}  # account_id -> (label, amount)
            for line in rec.tax_line_ids:
                if not line.tax_id.account_id:
                    raise UserError(_(
                        "Tax '%s' has no account configured.") % line.tax_id.name)
                key = line.tax_id.account_id.id
                label, amt = credits.get(key, (_('Taxes'), 0.0))
                credits[key] = (label, amt + line.amount)
            for line in rec.misc_line_ids:
                if not line.charge_id.account_id:
                    raise UserError(_(
                        "Charge '%s' has no account configured.")
                        % line.charge_id.name)
                key = line.charge_id.account_id.id
                label, amt = credits.get(key, (_('Misc Charges'), 0.0))
                credits[key] = (label, amt + line.amount)
            for account_id, (label, amount) in credits.items():
                lines.append((0, 0, {
                    'name': '%s - %s' % (label, rec.name),
                    'account_id': account_id,
                    'debit': 0.0,
                    'credit': amount,
                }))

            move = AccountMove.create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': rec.transfer_date,
                'ref': rec.name,
                'sa_transfer_id': rec.id,
                'company_id': rec.company_id.id,
                'line_ids': lines,
            })
            move.action_post()
            rec.move_id = move.id

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError(_("No accounting entry yet."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
        }

    # ----- Documentation -----

    def action_load_default_checklist(self):
        """Populate the standard transfer-documentation checklist.

        Existing items are preserved; only missing standard requirements are
        added so the action is safe to re-run.
        """
        default_items = [
            (_('Seller CNIC copy'), 'seller'),
            (_('Buyer CNIC copy'), 'buyer'),
            (_('Original allotment / registry file'), 'seller'),
            (_('Society / authority NOC'), 'authority'),
            (_('No Demand Certificate (NDC)'), 'authority'),
            (_('Transfer deed (signed)'), 'agency'),
            (_('FBR / CVT tax challan'), 'buyer'),
            (_('Stamp duty challan'), 'buyer'),
            (_('Passport-size photographs'), 'buyer'),
            (_('Transfer affidavit'), 'agency'),
        ]
        Checklist = self.env['sa.property.transfer.checklist']
        for rec in self:
            existing = set(rec.checklist_ids.mapped('name'))
            seq = 10
            for label, responsible in default_items:
                if label not in existing:
                    Checklist.create({
                        'transfer_id': rec.id,
                        'name': label,
                        'responsible': responsible,
                        'sequence': seq,
                    })
                seq += 10

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents - %s', self.name),
            'res_model': 'sa.property.document',
            'view_mode': 'list,form',
            'domain': [('transfer_id', '=', self.id)],
            'context': {
                'default_transfer_id': self.id,
                'default_property_id': self.property_id.id,
                'default_partner_id': self.to_partner_id.id,
                'default_document_type': 'transfer_deed',
            },
        }

    def action_print_deed(self):
        self.ensure_one()
        return self.env.ref(
            'sa_property_management.action_report_sa_transfer_deed').report_action(self)


class SaTransferTaxLine(models.Model):
    _name = 'sa.transfer.tax.line'
    _description = 'Property Transfer Tax Line'
    _order = 'sequence, id'

    transfer_id = fields.Many2one(
        'sa.property.transfer', required=True, ondelete='cascade')
    company_id = fields.Many2one(
        related='transfer_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='transfer_id.currency_id', store=True, readonly=True)
    sequence = fields.Integer(default=10)

    tax_id = fields.Many2one('sa.transfer.tax', required=True)
    name = fields.Char(related='tax_id.name', readonly=True)
    payer = fields.Selection(
        [('buyer', 'Buyer'),
         ('seller', 'Seller'),
         ('shared', 'Shared')],
        required=True, default='buyer')
    amount = fields.Monetary(currency_field='currency_id', required=True)


class SaTransferMiscLine(models.Model):
    _name = 'sa.transfer.misc.line'
    _description = 'Property Transfer Misc Line'
    _order = 'sequence, id'

    transfer_id = fields.Many2one(
        'sa.property.transfer', required=True, ondelete='cascade')
    company_id = fields.Many2one(
        related='transfer_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='transfer_id.currency_id', store=True, readonly=True)
    sequence = fields.Integer(default=10)

    charge_id = fields.Many2one('sa.misc.charge', required=True)
    name = fields.Char(related='charge_id.name', readonly=True)
    payer = fields.Selection(
        [('buyer', 'Buyer'),
         ('seller', 'Seller'),
         ('shared', 'Shared')],
        required=True, default='buyer')
    amount = fields.Monetary(currency_field='currency_id', required=True)


class SaTransferChecklist(models.Model):
    """A required-documents checklist item for an ownership transfer."""
    _name = 'sa.property.transfer.checklist'
    _description = 'Property Transfer Checklist Item'
    _order = 'sequence, id'

    transfer_id = fields.Many2one(
        'sa.property.transfer', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(
        related='transfer_id.company_id', store=True, readonly=True)
    property_id = fields.Many2one(
        related='transfer_id.property_id', store=True, readonly=True)
    sequence = fields.Integer(default=10)

    name = fields.Char(string='Requirement', required=True)
    responsible = fields.Selection(
        [('buyer', 'Buyer'),
         ('seller', 'Seller'),
         ('agency', 'Agency'),
         ('authority', 'Authority')],
        string='Provided By', default='seller')
    required = fields.Boolean(default=True)
    is_done = fields.Boolean(string='Received')
    received_date = fields.Date()
    document_id = fields.Many2one(
        'sa.property.document', string='Linked Document',
        ondelete='set null',
        domain="[('property_id', '=', property_id)]")
    note = fields.Char()

    @api.onchange('is_done')
    def _onchange_is_done(self):
        if self.is_done and not self.received_date:
            self.received_date = fields.Date.context_today(self)

