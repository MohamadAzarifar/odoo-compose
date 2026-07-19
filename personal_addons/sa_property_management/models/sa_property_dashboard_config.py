# -*- coding: utf-8 -*-
from odoo import fields, models


class SaPropertyDashboardConfig(models.Model):
    """Persists a per-user (or company-default) dashboard layout.

    The layout itself is an opaque JSON blob owned by the front-end component:
    visible/ordered sections, selected KPIs, saved filters and any user-defined
    custom widgets. Storing it as JSON keeps the schema flexible while still
    surviving logout and syncing across devices.
    """

    _name = 'sa.property.dashboard.config'
    _description = 'Property Dashboard Layout Configuration'

    user_id = fields.Many2one(
        'res.users', string='User', ondelete='cascade', index=True,
        help="Owner of this layout. Empty means the company-wide default.")
    is_default = fields.Boolean(
        string='Company Default', default=False,
        help="When set, this layout is used as the starting point for users "
             "who have not personalised their dashboard yet.")
    layout = fields.Json(string='Layout')

    _sql_constraints = [
        ('user_uniq', 'unique(user_id)',
         'A user can only have one saved dashboard layout.'),
    ]
