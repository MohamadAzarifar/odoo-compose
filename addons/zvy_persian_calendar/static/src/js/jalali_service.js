/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

export const jalaliService = {
    start() {
        return {
            isActive() {
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
                const lang = session.user_context?.lang || "";
                return Boolean(info.company_enabled || lang.startsWith("fa"));
            },
            getConfig() {
                return session.jalali_calendar || {};
            },
        };
    },
};

registry.category("services").add("jalali", jalaliService);
