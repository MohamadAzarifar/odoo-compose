/** @odoo-module **/

import { CalendarController } from "@web/views/calendar/calendar_controller";
import { patch } from "@web/core/utils/patch";
import { gregorianToJalali } from "@zvy_persian_calendar/js/jalali_core";
import {
    formatJalaliCurrentDateSuffix,
    formatJalaliDayHeader,
    formatJalaliMonthYear,
    formatJalaliWeekHeader,
    stepJalaliCalendarDate,
} from "@zvy_persian_calendar/js/jalali_calendar_utils";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

const { DateTime } = luxon;

patch(CalendarController.prototype, {
    get currentDate() {
        if (!isJalaliActive()) {
            return super.currentDate;
        }
        const meta = this.model.meta;
        const scale = meta.scale;
        if (this.env.isSmall && ["week", "month"].includes(scale)) {
            if (scale === "week" && this.model.rangeStart && this.model.rangeEnd) {
                return formatJalaliCurrentDateSuffix(this.model.rangeStart, scale, this.model.rangeEnd);
            }
            const date = meta.date || DateTime.now();
            return formatJalaliCurrentDateSuffix(date, scale);
        }
        return "";
    },

    get today() {
        if (!isJalaliActive()) {
            return super.today;
        }
        return String(gregorianToJalali(DateTime.now()).jd);
    },

    get currentYear() {
        if (!isJalaliActive()) {
            return super.currentYear;
        }
        return String(gregorianToJalali(this.date).jy);
    },

    get dayHeader() {
        if (!isJalaliActive()) {
            return super.dayHeader;
        }
        return formatJalaliDayHeader(this.date);
    },

    get weekHeader() {
        if (!isJalaliActive()) {
            return super.weekHeader;
        }
        const { rangeStart, rangeEnd } = this.model;
        return formatJalaliWeekHeader(rangeStart, rangeEnd);
    },

    get currentMonth() {
        if (!isJalaliActive()) {
            return super.currentMonth;
        }
        return formatJalaliMonthYear(this.date);
    },

    async setDate(move) {
        if (!isJalaliActive()) {
            return super.setDate(...arguments);
        }
        let date = null;
        switch (move) {
            case "next":
                date = stepJalaliCalendarDate(this.model.date, this.model.scale, "next");
                break;
            case "previous":
                date = stepJalaliCalendarDate(this.model.date, this.model.scale, "previous");
                break;
            case "today":
                date = DateTime.local().startOf("day");
                if (date.ts === this.date.startOf("day").ts) {
                    this.model.bus.trigger("SCROLL_TO_CURRENT_HOUR", false);
                }
                break;
        }
        await this.model.load({ date });
    },
});
