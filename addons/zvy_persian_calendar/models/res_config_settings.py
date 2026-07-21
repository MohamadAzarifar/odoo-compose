from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_jalali_calendar = fields.Boolean(
        related="company_id.use_jalali_calendar",
        readonly=False,
        string="Use Jalali Calendar",
        help="Show Jalali (Shamsi) dates in the backend for users whose "
             "personal preference is set to Default.",
    )
