# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    sa_operating_country_id = fields.Many2one(
        'res.country', string='Property Operating Country',
        help="Country whose property transfer taxes and charges are applied "
             "automatically. Defaults to the company's own country.")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sa_operating_country_id = fields.Many2one(
        'res.country', string='Property Operating Country',
        related='company_id.sa_operating_country_id', readonly=False,
        help="Select the country you operate in. Transfer taxes and "
             "miscellaneous charges tagged with this country (or with no "
             "country) are applied automatically on property transfers.")

    sa_default_area_uom = fields.Selection(
        [('marla', 'Marla'),
         ('kanal', 'Kanal'),
         ('sqft', 'Square Foot'),
         ('sqyd', 'Square Yard'),
         ('sqm', 'Square Meter'),
         ('acre', 'Acre')],
        string='Default Area Unit', default='marla',
        config_parameter='sa_property_management.default_area_uom')

    sa_enforce_area_limit = fields.Boolean(
        string='Enforce Project Land-Area Limit',
        config_parameter='sa_property_management.enforce_area_limit',
        help="Default for new projects: block creating properties whose "
             "combined area exceeds the project's total land area. Each "
             "project can still override this individually.")

    sa_property_journal_id = fields.Many2one(
        'account.journal', string='Property Sales Journal',
        domain="[('type', '=', 'sale')]",
        config_parameter='sa_property_management.property_journal_id')

    sa_transfer_journal_id = fields.Many2one(
        'account.journal', string='Property Transfer Journal',
        domain="[('type', 'in', ('sale', 'general'))]",
        config_parameter='sa_property_management.transfer_journal_id')

    sa_default_property_income_account_id = fields.Many2one(
        'account.account', string='Default Property Income Account',
        config_parameter='sa_property_management.default_income_account_id')

    sa_default_dealer_commission = fields.Float(
        string='Default Dealer Commission (%)', digits=(6, 2), default=2.0,
        config_parameter='sa_property_management.default_dealer_commission')

    sa_commission_expense_account_id = fields.Many2one(
        'account.account', string='Commission Expense Account',
        domain="[('account_type', '=', 'expense')]",
        config_parameter='sa_property_management.commission_expense_account_id',
        help="Expense account used on vendor bills generated for dealer and "
             "investor commissions. Falls back to the first expense account.")

    sa_penalty_income_account_id = fields.Many2one(
        'account.account', string='Penalty Income Account',
        domain="[('account_type', '=', 'income')]",
        config_parameter='sa_property_management.penalty_income_account_id',
        help="Income account used on invoices raised for late-payment "
             "penalties. Falls back to the property income account.")

    sa_currency_id = fields.Many2one(
        'res.currency', string='Property Currency (PKR recommended)',
        config_parameter='sa_property_management.currency_id')

    sa_default_payment_term_id = fields.Many2one(
        'account.payment.term', string='Default Payment Terms',
        config_parameter='sa_property_management.default_payment_term_id',
        help="Native Odoo payment terms pre-filled on new bookings and "
             "service assignments, and applied to the invoices they generate.")

    sa_send_payment_reminders = fields.Boolean(
        string='Send Installment Reminders',
        config_parameter='sa_property_management.send_payment_reminders',
        default=True,
        help="When enabled, the system schedules email reminders for due/overdue "
             "installments.")

    sa_require_biometric_verification = fields.Boolean(
        string='Require Biometric Verification',
        config_parameter='sa_property_management.require_biometric_verification',
        default=False,
        help="When enabled, a booking cannot be confirmed and a transfer "
             "cannot be completed until the customer has a verified biometric "
             "identity record.")

    sa_secugen_webapi_url = fields.Char(
        string='SecuGen WebAPI URL',
        config_parameter='sa_property_management.secugen_webapi_url',
        default='https://localhost:8443/SGIFPCapture',
        help="Local SecuGen WebAPI (SGIBioSrv) capture endpoint exposed on the "
             "operator's PC. The 'Scan with SecuGen' button on a verification "
             "posts to this URL. The service must trust this Odoo origin "
             "(CORS) and its certificate must be accepted by the browser.")
    sa_secugen_license = fields.Char(
        string='SecuGen License String',
        config_parameter='sa_property_management.secugen_license',
        help="Optional SecuGen WebAPI license string (licstr). Leave empty "
             "when running the service locally without a license restriction.")
    sa_secugen_min_quality = fields.Integer(
        string='Min Fingerprint Quality',
        config_parameter='sa_property_management.secugen_min_quality',
        default=50,
        help="Minimum acceptable image quality (0-100) requested from the "
             "scanner. Captures below it warn the operator to re-scan.")
    sa_secugen_timeout = fields.Integer(
        string='Capture Timeout (ms)',
        config_parameter='sa_property_management.secugen_timeout',
        default=10000,
        help="How long the scanner waits for a finger before timing out.")

    sa_doc_footer = fields.Char(
        string='Document Footer Note',
        config_parameter='sa_property_management.doc_footer',
        help="Branded footer line printed on property PDF documents "
             "(receipts, bookings, allocations, customer files).")
    sa_doc_tagline = fields.Char(
        string='Document Tagline',
        config_parameter='sa_property_management.doc_tagline',
        help="Short tagline printed under the company name on documents.")
