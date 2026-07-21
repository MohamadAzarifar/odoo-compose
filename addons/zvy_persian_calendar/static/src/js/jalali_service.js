/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { getUiLanguage } from "@zvy_persian_calendar/js/jalali_format";

/**
 * @returns {boolean}
 */
export function isJalaliActive() {
    if (session.jalali_calendar_enabled !== undefined) {
        return Boolean(session.jalali_calendar_enabled);
    }
    const info = session.jalali_calendar || {};
    if (info.user_preference === "disabled") {
        return false;
    }
    if (info.user_preference === "enabled") {
        return true;
    }
    const lang = getUiLanguage();
    return Boolean(info.company_enabled || lang.toLowerCase().startsWith("fa"));
}

export const jalaliService = {
    start() {
        return {
            isActive() {
                return isJalaliActive();
            },
            getConfig() {
                return session.jalali_calendar || {};
            },
        };
    },
};

registry.category("services").add("jalali", jalaliService);
