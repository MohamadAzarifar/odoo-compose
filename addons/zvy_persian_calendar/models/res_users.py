from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    use_jalali_calendar = fields.Selection(
        selection=[
            ("default", "Use company / language default"),
            ("enabled", "Always use Jalali calendar"),
            ("disabled", "Never use Jalali calendar"),
        ],
        string="Jalali Calendar",
        default="default",
        required=True,
        help="Override the company and language rules for Jalali calendar display.",
    )

    def _jalali_calendar_enabled(self):
        """Return whether Jalali UI should be active for this user."""
        self.ensure_one()
        preference = self.use_jalali_calendar
        if preference == "disabled":
            return False
        if preference == "enabled":
            return True
        company_enabled = self.company_id.use_jalali_calendar
        lang_fa = (self.lang or "").startswith("fa")
        return company_enabled or lang_fa
