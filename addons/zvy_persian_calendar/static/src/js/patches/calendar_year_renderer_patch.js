/** @odoo-module **/

import { useFullCalendar } from "@web/views/calendar/hooks/full_calendar_hook";
import { useCalendarPopover } from "@web/views/calendar/hooks/calendar_popover_hook";
import { CalendarYearRenderer } from "@web/views/calendar/calendar_year/calendar_year_renderer";
import { patch } from "@web/core/utils/patch";
import { renderToString } from "@web/core/utils/render";
import { gregorianToJalali } from "@zvy_persian_calendar/js/jalali_core";
import {
    isOutsideJalaliMonth,
    jalaliDayNumberFromJsDate,
    jalaliMonthAnchor,
    toFullCalendarVisibleRange,
} from "@zvy_persian_calendar/js/jalali_calendar_utils";
import { getJalaliMonthNames } from "@zvy_persian_calendar/js/jalali_format";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

import { useEffect, useRef } from "@odoo/owl";

const { DateTime } = luxon;

patch(CalendarYearRenderer.prototype, {
    setup() {
        this.months = isJalaliActive() ? getJalaliMonthNames() : luxon.Info.months();
        this.fcs = {};
        for (const month of this.months) {
            this.fcs[month] = useFullCalendar(
                `fullCalendar-${month}`,
                this.getOptionsForMonth(month)
            );
        }
        this.popover = useCalendarPopover(this.constructor.components.Popover);
        this.rootRef = useRef("root");

        useEffect(() => {
            this.updateSize();
            for (const fc of Object.values(this.fcs)) {
                fc.api?.updateSize();
            }
        });
    },

    get options() {
        const options = super.options;
        if (!isJalaliActive()) {
            return options;
        }
        return {
            ...options,
            // Keep the view *name* dayGridMonth so Odoo year SCSS (.fc-dayGridMonth-view)
            // still applies. Override definition to week-based dayGrid so Jalali months
            // that span two Gregorian months are not clipped by FC "other month" logic.
            initialView: "dayGridMonth",
            views: {
                dayGridMonth: {
                    type: "dayGrid",
                    duration: { weeks: 6 },
                    fixedWeekCount: false,
                },
            },
            showNonCurrentDates: true,
            fixedWeekCount: false,
            dayCellContent: (arg) => this.getJalaliYearDayCellContent(arg),
        };
    },

    getDateWithMonth(month) {
        if (!isJalaliActive()) {
            return super.getDateWithMonth(...arguments);
        }
        const jm = this.months.indexOf(month) + 1;
        return jalaliMonthAnchor(this.props.model.date, jm).toISO();
    },

    getOptionsForMonth(month) {
        if (!isJalaliActive()) {
            return super.getOptionsForMonth(...arguments);
        }
        const jm = this.months.indexOf(month) + 1;
        const start = jalaliMonthAnchor(this.props.model.date, jm);
        const { jy } = gregorianToJalali(start);
        const firstDay = this.props.model.firstDayOfWeek;
        const weekOffset = (start.weekday - firstDay + 7) % 7;
        const rangeStart = start.minus({ days: weekOffset });
        const rangeEnd = rangeStart.plus({ weeks: 6, days: -1 });
        return {
            ...this.options,
            initialDate: start.toISO(),
            visibleRange: toFullCalendarVisibleRange(rangeStart, rangeEnd),
            dayCellClassNames: (info) => {
                const classes = this.getDayCellClassNames(info);
                const cellDate = DateTime.fromJSDate(info.date, { zone: "UTC" });
                if (isOutsideJalaliMonth(cellDate, start)) {
                    classes.push("fc-day-other", "o_jalali_outside_month");
                }
                return classes;
            },
            viewDidMount: (info) => {
                this.viewDidMount(info);
                const titleEl = info.el.querySelector(".fc-toolbar-title");
                if (titleEl) {
                    titleEl.textContent = `${month} ${jy}`;
                }
                info.view.calendar.updateSize();
            },
        };
    },

    getJalaliYearDayCellContent(arg) {
        const day = jalaliDayNumberFromJsDate(arg.date, "month");
        return {
            html: renderToString("web.CalendarCommonRenderer.jalaliDayCell", { day }),
        };
    },
});
