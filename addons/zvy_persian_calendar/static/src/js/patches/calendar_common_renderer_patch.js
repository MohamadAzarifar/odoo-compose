/** @odoo-module **/

import { renderToString } from "@web/core/utils/render";
import { patch } from "@web/core/utils/patch";
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import {
    isOutsideJalaliMonth,
    jalaliDayNumberFromJsDate,
    jalaliHeaderTemplateProps,
    toFullCalendarVisibleRange,
} from "@zvy_persian_calendar/js/jalali_calendar_utils";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

const { DateTime } = luxon;

const SCALE_TO_FC_VIEW_JALALI = {
    day: "timeGridDay",
    week: "timeGridWeek",
    // Keep dayGridMonth (week rows + Odoo SCSS). Jalali bounds come from visibleRange.
    month: "dayGridMonth",
};

patch(CalendarCommonRenderer.prototype, {
    get options() {
        const options = super.options;
        if (!isJalaliActive()) {
            return options;
        }
        const scale = this.props.model.scale;
        const patched = {
            ...options,
            initialView: SCALE_TO_FC_VIEW_JALALI[scale] || options.initialView,
            // Keep stock dayCellClassNames → this.getDayCellClassNames (patched below).
            dayCellContent: (arg) => this.getJalaliDayCellContent(arg),
        };
        if (scale === "month") {
            patched.views = {
                dayGridMonth: {
                    type: "dayGrid",
                    duration: { weeks: 6 },
                    fixedWeekCount: false,
                },
            };
            patched.visibleRange = toFullCalendarVisibleRange(
                this.props.model.rangeStart,
                this.props.model.rangeEnd
            );
            // Keep overflow weeks visible; cells outside the Jalali month are muted via classNames.
            patched.showNonCurrentDates = true;
            patched.fixedWeekCount = false;
        }
        return patched;
    },

    headerTemplateProps(date) {
        if (!isJalaliActive()) {
            return super.headerTemplateProps(...arguments);
        }
        return jalaliHeaderTemplateProps(date, this.props.model.scale);
    },

    getDayCellClassNames(info) {
        const classes = super.getDayCellClassNames(...arguments);
        if (!isJalaliActive() || this.props.model.scale !== "month") {
            return classes;
        }
        const cellDate = DateTime.fromJSDate(info.date, { zone: "UTC" });
        if (isOutsideJalaliMonth(cellDate, this.props.model.date)) {
            classes.push("fc-day-other", "o_jalali_outside_month");
        }
        return classes;
    },

    /**
     * @param {import("@fullcalendar/core").DayCellContentArg} arg
     */
    getJalaliDayCellContent(arg) {
        if (this.props.model.scale !== "month") {
            return true;
        }
        const day = jalaliDayNumberFromJsDate(arg.date, "month");
        return {
            html: renderToString("web.CalendarCommonRenderer.jalaliDayCell", { day }),
        };
    },
});