/** @odoo-module **/

import { CalendarModel } from "@web/views/calendar/calendar_model";
import { patch } from "@web/core/utils/patch";
import { computeJalaliCalendarRange } from "@zvy_persian_calendar/js/jalali_calendar_utils";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

patch(CalendarModel.prototype, {
    /**
     * @override
     * Use Jalali month / year boundaries (and locale week start) when active.
     */
    computeRange() {
        if (!isJalaliActive()) {
            return super.computeRange(...arguments);
        }
        const { scale, date, firstDayOfWeek } = this.meta;
        return computeJalaliCalendarRange({
            scale,
            date,
            firstDayOfWeek,
            monthOverflow: this.monthOverflow,
        });
    },
});
