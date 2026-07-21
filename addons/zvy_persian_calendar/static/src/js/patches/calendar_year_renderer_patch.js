/** @odoo-module **/

import { useFullCalendar } from "@web/views/calendar/hooks/full_calendar_hook";
import { useCalendarPopover } from "@web/views/calendar/hooks/calendar_popover_hook";
import { CalendarYearRenderer } from "@web/views/calendar/calendar_year/calendar_year_renderer";
import { patch } from "@web/core/utils/patch";
import { renderToString } from "@web/core/utils/render";
import { gregorianToJalali } from "@zvy_persian_calendar/js/jalali_core";
import {
    jalaliDayNumberFromJsDate,
    jalaliMonthAnchor,
    toFullCalendarVisibleRange,
} from "@zvy_persian_calendar/js/jalali_calendar_utils";
import { getJalaliMonthNames } from "@zvy_persian_calendar/js/jalali_format";
import { jalaliMonthEnd } from "@zvy_persian_calendar/js/jalali_picker_utils";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

import { useEffect, useRef } from "@odoo/owl";

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
        });
    },

    get options() {
        const options = super.options;
        if (!isJalaliActive()) {
            return options;
        }
        return {
            ...options,
            initialView: "dayGrid",
            showNonCurrentDates: false,
            dayCellContent: this.getJalaliYearDayCellContent.bind(this),
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
        const end = jalaliMonthEnd(jy, jm);
        return {
            ...this.options,
            initialDate: start.toISO(),
            visibleRange: toFullCalendarVisibleRange(start, end),
            viewDidMount: (info) => {
                this.viewDidMount(info);
                const titleEl = info.el.querySelector(".fc-toolbar-title");
                if (titleEl) {
                    titleEl.textContent = `${month} ${jy}`;
                }
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
