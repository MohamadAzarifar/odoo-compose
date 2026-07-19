# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaKiborRate(models.Model):
    """Effective-dated KIBOR (Karachi Interbank Offered Rate) entries.

    Used as the floating base for late-payment penalties when a payment plan
    is configured with the KIBOR + spread penalty method. The applicable rate
    for any date is the most recent entry on or before that date for the same
    tenor.
    """
    _name = 'sa.kibor.rate'
    _description = 'KIBOR Rate'
    _order = 'effective_date desc, tenor'

    name = fields.Char(compute='_compute_name', store=True)
    effective_date = fields.Date(
        required=True, default=fields.Date.context_today, index=True,
        help="Date from which this rate applies.")
    tenor = fields.Selection(
        [('1m', '1 Month'),
         ('3m', '3 Months'),
         ('6m', '6 Months'),
         ('12m', '12 Months')],
        required=True, default='6m', index=True,
        help="KIBOR tenor. Penalty configuration selects which tenor to use.")
    rate = fields.Float(
        string='Rate (%)', digits=(6, 3), required=True,
        help="Annualised KIBOR percentage for this tenor and date.")
    active = fields.Boolean(default=True)
    note = fields.Char()

    _sql_constraints = [
        ('date_tenor_uniq', 'unique(effective_date, tenor)',
         'A KIBOR rate already exists for this date and tenor.'),
        ('rate_positive', 'CHECK(rate >= 0)', 'Rate cannot be negative.'),
    ]

    @api.depends('effective_date', 'tenor', 'rate')
    def _compute_name(self):
        labels = dict(self._fields['tenor'].selection)
        for rec in self:
            rec.name = '%s %s @ %.3f%%' % (
                rec.effective_date or '',
                labels.get(rec.tenor, rec.tenor or ''),
                rec.rate or 0.0)

    @api.model
    def get_rate_for(self, date, tenor='6m'):
        """Return the applicable annual rate (%) for a date and tenor.

        Picks the most recent active entry on or before ``date``. Returns 0.0
        when no rate is available.
        """
        if not date:
            date = fields.Date.context_today(self)
        entry = self.search([
            ('effective_date', '<=', date),
            ('tenor', '=', tenor),
            ('active', '=', True),
        ], order='effective_date desc', limit=1)
        return entry.rate if entry else 0.0
