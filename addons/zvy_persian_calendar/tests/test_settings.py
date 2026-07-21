from odoo.tests import tagged, TransactionCase


@tagged("post_install", "-at_install")
class TestJalaliSettings(TransactionCase):
    def setUp(self):
        super().setUp()
        self.user = self.env.ref("base.user_admin")
        self.company = self.user.company_id

    def test_company_flag_enables_default_users(self):
        self.company.use_jalali_calendar = True
        self.user.use_jalali_calendar = "default"
        self.assertTrue(self.user._jalali_calendar_enabled())

    def test_user_can_force_disable(self):
        self.company.use_jalali_calendar = True
        self.user.use_jalali_calendar = "disabled"
        self.assertFalse(self.user._jalali_calendar_enabled())

    def test_user_can_force_enable(self):
        self.company.use_jalali_calendar = False
        self.user.use_jalali_calendar = "enabled"
        self.assertTrue(self.user._jalali_calendar_enabled())

    def test_persian_language_enables_default_users(self):
        self.company.use_jalali_calendar = False
        self.user.use_jalali_calendar = "default"
        self.user.lang = "fa_IR"
        self.assertTrue(self.user._jalali_calendar_enabled())

    def test_session_info_exposes_flag(self):
        self.company.use_jalali_calendar = True
        info = self.env["ir.http"].session_info()
        self.assertTrue(info["jalali_calendar_enabled"])
        self.assertTrue(info["jalali_calendar"]["company_enabled"])
