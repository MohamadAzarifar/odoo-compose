/** @odoo-module **/

import * as dates from "@web/core/l10n/dates";
import * as formatters from "@web/views/fields/formatters";
import { patch } from "@web/core/utils/patch";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

patch(formatters, {
    formatDate(value, options = {}) {
        if (!isJalaliActive()) {
            return super.formatDate(...arguments);
        }
        if (options.numeric) {
            return dates.formatDate(value, options);
        }
        return dates.toLocaleDateString(value);
    },

    formatDateTime(value, options = {}) {
        if (!isJalaliActive()) {
            return super.formatDateTime(...arguments);
        }
        if (options.numeric) {
            if (options.showTime === false) {
                return dates.formatDate(value, options);
            }
            return dates.formatDateTime(value, options);
        }
        return dates.toLocaleDateTimeString(value, options);
    },
});
