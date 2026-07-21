# -*- coding: utf-8 -*-
{
    "name": "ZVY Persian Calendar",
    "version": "19.0.1.0.1",
    "category": "Localization",
    "summary": "Jalali (Shamsi) calendar presentation layer for Odoo backend UI",
    "description": """
Persian (Jalali) Calendar
=========================

Shows Jalali dates in the Odoo backend while keeping Gregorian ISO storage
in the database. Includes company and user-level toggles and a tested
JavaScript conversion core for later UI patches.
    """,
    "author": "ZVY",
    "license": "LGPL-3",
    "depends": ["web", "base_setup"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/res_users_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "zvy_persian_calendar/static/lib/jalaali/jalaali.js",
            "zvy_persian_calendar/static/src/js/jalali_core.js",
            "zvy_persian_calendar/static/src/js/jalali_format.js",
            "zvy_persian_calendar/static/src/js/jalali_service.js",
        ],
        "web.assets_unit_tests": [
            "zvy_persian_calendar/static/src/js/tests/jalali_core.test.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
