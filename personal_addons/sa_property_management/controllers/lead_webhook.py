# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class SaLeadWebhookController(http.Controller):
    """Public inbound webhook for capturing leads from third-party platforms
    (Meta Lead Ads, Apollo, Zapier/Make, website forms, ...). Each lead source
    integration has its own unguessable token in the URL."""

    def _json(self, payload, status=200):
        return Response(json.dumps(payload), status=status,
                        content_type='application/json')

    def _find_source(self, token):
        return request.env['sa.lead.source'].sudo().search(
            [('token', '=', token), ('active', '=', True)], limit=1)

    @http.route('/sa/lead/webhook/<string:token>', type='http', auth='public',
                methods=['GET'], csrf=False, save_session=False)
    def lead_webhook_verify(self, token, **params):
        """GET handler. Supports Meta's webhook subscription handshake
        (hub.challenge) and a simple liveness check otherwise."""
        source = self._find_source(token)
        if not source:
            return self._json({'status': 'error', 'message': 'invalid token'},
                              status=404)
        challenge = params.get('hub.challenge') or params.get('hub_challenge')
        if challenge:
            return Response(challenge, status=200, content_type='text/plain')
        return self._json({'status': 'ok', 'source': source.name})

    @http.route('/sa/lead/webhook/<string:token>', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def lead_webhook(self, token, **post):
        source = self._find_source(token)
        if not source:
            return self._json({'status': 'error', 'message': 'invalid token'},
                              status=404)
        payload = {}
        try:
            raw = request.httprequest.get_data(as_text=True)
            if raw:
                payload = json.loads(raw)
        except Exception:
            payload = {}
        if not isinstance(payload, dict) or not payload:
            # Fall back to form-encoded fields.
            payload = {k: v for k, v in post.items()}
        try:
            lead = source.sudo()._create_lead_from_payload(payload)
        except Exception as exc:  # noqa: BLE001 - report failure to caller
            _logger.warning("Lead webhook failed for source %s: %s",
                            source.id, exc)
            return self._json({'status': 'error', 'message': 'bad payload'},
                              status=400)
        return self._json({'status': 'ok', 'lead_id': lead.id})
