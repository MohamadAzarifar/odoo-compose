# -*- coding: utf-8 -*-
{
    "name": "ZVY Persian Calendar",
    "version": "19.0.1.0.6",
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
            (
                "before",
                "web/static/src/core/datetime/datetimepicker_service.js",
                "zvy_persian_calendar/static/lib/jalaali/jalaali.js",
            ),
            (
                "before",
                "web/static/src/core/datetime/datetimepicker_service.js",
                "zvy_persian_calendar/static/src/js/jalali_core.js",
            ),
            (
                "before",
                "web/static/src/core/datetime/datetimepicker_service.js",
                "zvy_persian_calendar/static/src/js/jalali_format.js",
            ),
            (
                "before",
                "web/static/src/core/datetime/datetimepicker_service.js",
                "zvy_persian_calendar/static/src/js/jalali_luxon_format.js",
            ),
            (
                "before",
                "web/static/src/core/datetime/datetimepicker_service.js",
                "zvy_persian_calendar/static/src/js/jalali_service.js",
            ),
            (
                "before",
                "web/static/src/core/datetime/datetimepicker_service.js",
                "zvy_persian_calendar/static/src/js/patches/dates_patch.js",
            ),
            "zvy_persian_calendar/static/src/js/jalali_picker_utils.js",
            "zvy_persian_calendar/static/src/js/patches/formatters_patch.js",
            "zvy_persian_calendar/static/src/js/patches/datetime_picker_patch.js",
            "zvy_persian_calendar/static/src/js/patches/datetime_field_patch.js",
            "zvy_persian_calendar/static/src/xml/datetime_picker.xml",
            "zvy_persian_calendar/static/src/xml/datetime_input.xml",
            "zvy_persian_calendar/static/src/scss/jalali_calendar.scss",
        ],
        "web.assets_unit_tests": [
            "zvy_persian_calendar/static/src/js/tests/jalali_core.test.js",
            "zvy_persian_calendar/static/src/js/tests/jalali_luxon_format.test.js",
            "zvy_persian_calendar/static/src/js/tests/jalali_picker_utils.test.js",
            "zvy_persian_calendar/static/src/js/tests/jalali_parse.test.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
