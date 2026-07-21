from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_jalali_calendar = fields.Boolean(
        string="Use Jalali Calendar",
        default=False,
        help="When enabled, users whose preference is 'Default' see Jalali "
             "(Shamsi) dates in the backend UI. Storage remains Gregorian.",
    )
