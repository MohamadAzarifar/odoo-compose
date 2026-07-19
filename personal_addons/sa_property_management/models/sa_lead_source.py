# -*- coding: utf-8 -*-
import uuid

from odoo import api, fields, models, _


# Common inbound payload keys mapped to crm.lead fields. Keeps the webhook and
# the manual import tolerant of the many shapes Meta/Apollo/Zapier/etc. send.
_NAME_KEYS = ('name', 'full_name', 'fullname', 'contact_name', 'lead_name')
_EMAIL_KEYS = ('email', 'email_address', 'work_email', 'email_from')
_PHONE_KEYS = ('phone', 'phone_number', 'mobile', 'mobile_number', 'tel')
_COMPANY_KEYS = ('company', 'company_name', 'organization', 'partner_name')
_MESSAGE_KEYS = ('message', 'description', 'notes', 'comments', 'comment', 'body')


class SaLeadSource(models.Model):
    """A per-user lead-source integration. Each source exposes a unique,
    unguessable webhook URL that external platforms (Meta Lead Ads, Apollo,
    Zapier, Make, a website form, ...) can POST leads to. Leads land in the
    native CRM pipeline tagged with this source and its UTM attribution."""
    _name = 'sa.lead.source'
    _description = 'Lead Source Integration'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    platform = fields.Selection(
        [('meta', 'Meta (Facebook / Instagram)'),
         ('google', 'Google Ads'),
         ('apollo', 'Apollo'),
         ('tiktok', 'TikTok'),
         ('linkedin', 'LinkedIn'),
         ('zapier', 'Zapier / Make'),
         ('website', 'Website Form'),
         ('whatsapp', 'WhatsApp'),
         ('other', 'Other')],
        required=True, default='website', tracking=True)

    user_id = fields.Many2one(
        'res.users', string='Owner', required=True,
        default=lambda self: self.env.user,
        help="The user who owns and manages this integration.")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)

    token = fields.Char(
        string='Webhook Token', copy=False, readonly=True, index=True,
        default=lambda self: uuid.uuid4().hex,
        help="Secret token embedded in the webhook URL.")
    webhook_url = fields.Char(
        string='Webhook URL', compute='_compute_webhook_url')
    api_key = fields.Char(
        string='API Key / Access Token',
        help="Optional credential stored for platforms that require one.")

    # --- How captured leads are created ---
    team_id = fields.Many2one('crm.team', string='Sales Team')
    lead_user_id = fields.Many2one(
        'res.users', string='Assign Leads To',
        help="Salesperson set on leads created from this source.")
    create_as_opportunity = fields.Boolean(
        string='Create as Opportunity',
        help="Create opportunities directly instead of unqualified leads.")
    utm_source_id = fields.Many2one('utm.source', string='UTM Source')
    utm_medium_id = fields.Many2one('utm.medium', string='UTM Medium')
    tag_ids = fields.Many2many('crm.tag', string='Default Tags')

    lead_count = fields.Integer(compute='_compute_lead_count')
    note = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = uuid.uuid4().hex
        return super().create(vals_list)

    def _compute_webhook_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url') or ''
        base = base.rstrip('/')
        for rec in self:
            rec.webhook_url = '%s/sa/lead/webhook/%s' % (base, rec.token or '')

    def _compute_lead_count(self):
        Lead = self.env['crm.lead']
        for rec in self:
            rec.lead_count = Lead.search_count(
                [('sa_source_id', '=', rec.id)]) if rec.id else 0

    def action_rotate_token(self):
        for rec in self:
            rec.token = uuid.uuid4().hex
        return True

    def action_view_leads(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Leads'),
            'res_model': 'crm.lead',
            'view_mode': 'list,kanban,form',
            'domain': [('sa_source_id', '=', self.id)],
            'context': {'default_sa_source_id': self.id},
        }

    def action_quick_import(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quick Import Leads'),
            'res_model': 'sa.lead.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_source_id': self.id},
        }

    # --- Lead creation ---
    @staticmethod
    def _pick(payload, keys):
        for key in keys:
            val = payload.get(key)
            if val:
                return str(val).strip()
        return ''

    def _prepare_lead_vals(self, payload):
        """Map a tolerant inbound payload dict to crm.lead values."""
        self.ensure_one()
        payload = {str(k).lower(): v for k, v in (payload or {}).items()}
        name = self._pick(payload, _NAME_KEYS)
        if not name:
            first = self._pick(payload, ('first_name', 'firstname'))
            last = self._pick(payload, ('last_name', 'lastname', 'surname'))
            name = ' '.join(p for p in (first, last) if p)
        email = self._pick(payload, _EMAIL_KEYS)
        phone = self._pick(payload, _PHONE_KEYS)
        company = self._pick(payload, _COMPANY_KEYS)
        message = self._pick(payload, _MESSAGE_KEYS)

        title = name or email or phone or _('New Lead')
        vals = {
            'name': _('%s - %s', self.name, title),
            'contact_name': name or False,
            'email_from': email or False,
            'phone': phone or False,
            'partner_name': company or False,
            'description': message or False,
            'type': 'opportunity' if self.create_as_opportunity else 'lead',
            'sa_source_id': self.id,
            'company_id': self.company_id.id,
        }
        if self.team_id:
            vals['team_id'] = self.team_id.id
        if self.lead_user_id:
            vals['user_id'] = self.lead_user_id.id
        if self.utm_source_id:
            vals['source_id'] = self.utm_source_id.id
        if self.utm_medium_id:
            vals['medium_id'] = self.utm_medium_id.id
        if self.tag_ids:
            vals['tag_ids'] = [(6, 0, self.tag_ids.ids)]
        return vals

    def _create_lead_from_payload(self, payload):
        self.ensure_one()
        lead = self.env['crm.lead'].create(self._prepare_lead_vals(payload))
        lead.message_post(
            body=_('Lead captured from %s integration.', self.name))
        return lead
