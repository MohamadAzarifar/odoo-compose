# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SaPaymentPlan(models.Model):
    """Reusable payment plan template.

    Schedule shape:
        Down payment (% of total)
        + N regular installments (frequency: monthly / quarterly / etc.)
        + optional balloon (extra) lines
        + optional on-possession charge (% of total)

    The sum of all percentages must equal 100%.
    """
    _name = 'sa.payment.plan'
    _description = 'Property Payment Plan'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        related='company_id.currency_id', store=True, readonly=True)

    down_payment_percent = fields.Float(
        string='Down Payment (%)', digits=(6, 2), default=20.0, required=True)
    installment_count = fields.Integer(
        string='Number of Installments', default=12, required=True)
    installment_percent_each = fields.Float(
        string='% Per Installment', digits=(8, 4),
        compute='_compute_installment_percent_each', store=True,
        help="Computed: (100 - down% - on-possession% - sum(extra%)) / count.")
    frequency = fields.Selection(
        [('monthly', 'Monthly'),
         ('bi_monthly', 'Bi-Monthly'),
         ('quarterly', 'Quarterly'),
         ('half_yearly', 'Half-Yearly'),
         ('yearly', 'Yearly')],
        default='monthly', required=True)
    on_possession_percent = fields.Float(
        string='On Possession (%)', digits=(6, 2), default=0.0)
    extra_line_ids = fields.One2many(
        'sa.payment.plan.line', 'plan_id', string='Extra / Balloon Charges',
        copy=True)

    total_percent = fields.Float(
        string='Total %', digits=(8, 2), compute='_compute_total_percent', store=True)
    note = fields.Text()

    # --- Late-payment penalty policy ---
    penalty_type = fields.Selection(
        [('none', 'No Penalty'),
         ('flat', 'Flat Amount / Day'),
         ('percent', '% of Overdue / Day'),
         ('kibor', 'KIBOR + Spread (annual)')],
        string='Penalty Method', default='none', required=True,
        help="How late-payment penalties are charged on overdue installments.")
    penalty_value = fields.Float(
        string='Penalty Value', digits=(12, 4),
        help="For 'Flat Amount / Day' this is the currency amount per day "
             "late. For '% of Overdue / Day' this is the daily percentage "
             "applied to the outstanding amount.")
    penalty_kibor_tenor = fields.Selection(
        [('1m', '1 Month'),
         ('3m', '3 Months'),
         ('6m', '6 Months'),
         ('12m', '12 Months')],
        string='KIBOR Tenor', default='6m',
        help="KIBOR tenor used as the penalty base.")
    penalty_kibor_spread = fields.Float(
        string='KIBOR Spread (%)', digits=(6, 3),
        help="Spread added to the applicable annual KIBOR rate.")
    penalty_grace_days = fields.Integer(
        string='Grace Days', default=0,
        help="Number of days after the due date before a penalty starts "
             "accruing.")

    _sql_constraints = [
        ('installment_count_positive', 'CHECK(installment_count > 0)',
         'Number of installments must be greater than zero.'),
        ('down_payment_range', 'CHECK(down_payment_percent >= 0 AND down_payment_percent <= 100)',
         'Down payment must be between 0 and 100%.'),
        ('penalty_grace_days_positive', 'CHECK(penalty_grace_days >= 0)',
         'Grace days cannot be negative.'),
    ]

    @api.depends('down_payment_percent', 'installment_count',
                 'on_possession_percent', 'extra_line_ids.percent')
    def _compute_installment_percent_each(self):
        for rec in self:
            extras = sum(rec.extra_line_ids.mapped('percent'))
            remaining = 100.0 - (rec.down_payment_percent or 0.0) \
                - (rec.on_possession_percent or 0.0) - extras
            rec.installment_percent_each = (
                remaining / rec.installment_count
                if rec.installment_count else 0.0)

    @api.depends('down_payment_percent', 'installment_count',
                 'installment_percent_each', 'on_possession_percent',
                 'extra_line_ids.percent')
    def _compute_total_percent(self):
        for rec in self:
            rec.total_percent = (
                (rec.down_payment_percent or 0.0)
                + (rec.installment_count or 0) * (rec.installment_percent_each or 0.0)
                + sum(rec.extra_line_ids.mapped('percent'))
                + (rec.on_possession_percent or 0.0)
            )

    @api.constrains('down_payment_percent', 'on_possession_percent', 'extra_line_ids')
    def _check_total_percent(self):
        for rec in self:
            extras = sum(rec.extra_line_ids.mapped('percent'))
            base = (rec.down_payment_percent or 0.0) \
                + (rec.on_possession_percent or 0.0) + extras
            if base > 100.0:
                raise ValidationError(_(
                    "Plan '%s': Down payment + on-possession + extras (%.2f%%) "
                    "exceed 100%%. Reduce one of these values."
                ) % (rec.name, base))

    def _frequency_delta(self):
        """Return a relativedelta matching the configured frequency."""
        self.ensure_one()
        mapping = {
            'monthly': relativedelta(months=1),
            'bi_monthly': relativedelta(months=2),
            'quarterly': relativedelta(months=3),
            'half_yearly': relativedelta(months=6),
            'yearly': relativedelta(years=1),
        }
        return mapping.get(self.frequency, relativedelta(months=1))

    def generate_schedule(self, total_price, start_date):
        """Return a list of dicts describing each installment, in order.

        Each dict: {sequence, name, due_date, amount, line_type}
        line_type ∈ {'down_payment', 'installment', 'extra', 'on_possession'}

        Pure helper — does not touch the database. Caller persists results.
        """
        self.ensure_one()
        total_price = total_price or 0.0
        rounding = self.currency_id.rounding or 0.01

        schedule = []
        seq = 1
        running_total = 0.0
        delta = self._frequency_delta()

        if self.down_payment_percent:
            amt = self.currency_id.round(
                total_price * self.down_payment_percent / 100.0) if self.currency_id \
                else round(total_price * self.down_payment_percent / 100.0, 2)
            schedule.append({
                'sequence': seq,
                'name': _('Down Payment'),
                'due_date': start_date,
                'amount': amt,
                'line_type': 'down_payment',
            })
            seq += 1
            running_total += amt

        # Build a quick lookup of extras keyed by trigger installment number
        extras_by_index = {}
        for line in self.extra_line_ids.sorted('after_installment'):
            extras_by_index.setdefault(line.after_installment, []).append(line)

        per_inst = self.currency_id.round(
            total_price * self.installment_percent_each / 100.0) if self.currency_id \
            else round(total_price * self.installment_percent_each / 100.0, 2)

        current_date = start_date
        for i in range(1, self.installment_count + 1):
            current_date = current_date + delta
            schedule.append({
                'sequence': seq,
                'name': _('Installment %s/%s', i, self.installment_count),
                'due_date': current_date,
                'amount': per_inst,
                'line_type': 'installment',
            })
            seq += 1
            running_total += per_inst
            for line in extras_by_index.get(i, []):
                amt = self.currency_id.round(
                    total_price * line.percent / 100.0) if self.currency_id \
                    else round(total_price * line.percent / 100.0, 2)
                schedule.append({
                    'sequence': seq,
                    'name': line.name,
                    'due_date': current_date,
                    'amount': amt,
                    'line_type': 'extra',
                })
                seq += 1
                running_total += amt

        if self.on_possession_percent:
            amt = self.currency_id.round(
                total_price * self.on_possession_percent / 100.0) if self.currency_id \
                else round(total_price * self.on_possession_percent / 100.0, 2)
            # Adjust the on-possession line to absorb rounding so the schedule
            # sums exactly to total_price.
            diff = total_price - (running_total + amt)
            if abs(diff) >= rounding:
                amt += diff
            schedule.append({
                'sequence': seq,
                'name': _('On Possession'),
                'due_date': current_date,
                'amount': amt,
                'line_type': 'on_possession',
            })
        else:
            # No on-possession line: absorb rounding in the last installment.
            diff = total_price - running_total
            if schedule and abs(diff) >= rounding:
                schedule[-1]['amount'] += diff

        return schedule

    def compute_penalty(self, residual, days_overdue, ref_date=None):
        """Return the penalty amount for an overdue installment.

        ``residual`` is the outstanding amount, ``days_overdue`` the number of
        days past the due date. Grace days are subtracted before charging.
        Pure helper — does not touch the database.
        """
        self.ensure_one()
        if self.penalty_type == 'none' or residual <= 0 or days_overdue <= 0:
            return 0.0
        chargeable_days = max(days_overdue - (self.penalty_grace_days or 0), 0)
        if chargeable_days <= 0:
            return 0.0
        if self.penalty_type == 'flat':
            penalty = (self.penalty_value or 0.0) * chargeable_days
        elif self.penalty_type == 'percent':
            penalty = residual * (self.penalty_value or 0.0) / 100.0 \
                * chargeable_days
        elif self.penalty_type == 'kibor':
            annual = self.env['sa.kibor.rate'].get_rate_for(
                ref_date or fields.Date.context_today(self),
                self.penalty_kibor_tenor or '6m')
            annual += (self.penalty_kibor_spread or 0.0)
            penalty = residual * annual / 100.0 / 365.0 * chargeable_days
        else:
            penalty = 0.0
        return self.currency_id.round(penalty) if self.currency_id else round(penalty, 2)


class SaPaymentPlanLine(models.Model):
    """Extra/balloon line within a payment plan (e.g. 10% extra at month 12)."""
    _name = 'sa.payment.plan.line'
    _description = 'Payment Plan Extra Line'
    _order = 'after_installment, id'

    plan_id = fields.Many2one(
        'sa.payment.plan', required=True, ondelete='cascade')
    name = fields.Char(required=True, translate=True,
                       default=lambda self: _('Balloon Payment'))
    after_installment = fields.Integer(
        required=True, default=1,
        help="This extra amount falls due alongside this installment number.")
    percent = fields.Float(
        string='% of Sale Price', digits=(6, 2), required=True, default=10.0)

    _sql_constraints = [
        ('percent_range', 'CHECK(percent > 0 AND percent <= 100)',
         'Extra line percent must be between 0 and 100.'),
        ('after_installment_positive', 'CHECK(after_installment > 0)',
         'After-installment number must be greater than zero.'),
    ]

    @api.constrains('after_installment', 'plan_id')
    def _check_after_installment(self):
        for rec in self:
            if rec.plan_id and rec.after_installment > rec.plan_id.installment_count:
                raise ValidationError(_(
                    "Extra line '%s' references installment %s but the plan "
                    "only has %s installments."
                ) % (rec.name, rec.after_installment,
                     rec.plan_id.installment_count))
