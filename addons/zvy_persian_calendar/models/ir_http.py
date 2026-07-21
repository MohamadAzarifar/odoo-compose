from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        if self.env.user._is_internal():
            user = self.env.user
            result["jalali_calendar_enabled"] = user._jalali_calendar_enabled()
            result["jalali_calendar"] = {
                "enabled": user._jalali_calendar_enabled(),
                "company_enabled": user.company_id.use_jalali_calendar,
                "user_preference": user.use_jalali_calendar,
            }
        return result
