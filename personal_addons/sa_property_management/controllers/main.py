# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

# Models that expose a QR token + public status payload, in lookup order.
VERIFY_MODELS = (
    'sa.property.booking',
    'sa.property.installment',
    'sa.property',
    'sa.property.transfer',
    'sa.dealer.allocation',
    'res.partner',
)


class SaQrVerifyController(http.Controller):

    @http.route(['/sa/verify/<string:token>'], type='http',
                auth='public', website=False, sitemap=False)
    def sa_verify(self, token, **kwargs):
        record = None
        if token:
            for model in VERIFY_MODELS:
                Model = request.env[model].sudo()
                if 'sa_qr_token' not in Model._fields:
                    continue
                rec = Model.search([('sa_qr_token', '=', token)], limit=1)
                if rec:
                    record = rec
                    break

        if not record:
            return request.render(
                'sa_property_management.sa_verify_not_found', {})

        info = record._sa_status_info()
        company = record.company_id if 'company_id' in record._fields else request.env.company
        return request.render('sa_property_management.sa_verify_page', {
            'info': info,
            'company': company or request.env.company,
        })
