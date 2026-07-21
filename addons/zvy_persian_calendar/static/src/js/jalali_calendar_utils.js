/** @odoo-module **/

import { gregorianToJalali, jalaliMonthLength, jalaliToGregorian } from "./jalali_core";
import {
    formatJalali,
    getJalaliMonthNames,
    getJalaliMonthNamesShort,
} from "./jalali_format";
import {
    addJalaliMonths,
    jalaliMonthEnd,
    jalaliMonthStart,
} from "./jalali_picker_utils";

const { DateTime } = luxon;

/**
 * @param {luxon.DateTime} date
 * @param {number} firstDayOfWeek Odoo calendar firstDayOfWeek (0=Sun, 1=Mon, …)
 * @returns {luxon.DateTime}
 */
export function startOfWeekForCalendar(date, firstDayOfWeek) {
    // Same formula as CalendarModel.computeRange
    const currentWeekOffset = (date.weekday - firstDayOfWeek + 7) % 7;
    return date.minus({ days: currentWeekOffset }).startOf("day");
}

/**
 * Range for calendar model (mirrors CalendarModel.computeRange, Jalali month).
 *
 * @param {object} params
 * @param {"day"|"week"|"month"|"year"} params.scale
 * @param {luxon.DateTime} params.date
 * @param {number} params.firstDayOfWeek
 * @param {boolean} params.monthOverflow
 * @returns {{ start: luxon.DateTime, end: luxon.DateTime }}
 */
export function computeJalaliCalendarRange({ scale, date, firstDayOfWeek, monthOverflow }) {
    let start = date;
    let end = date;

    if (scale === "day") {
        start = date.startOf("day");
        end = date.endOf("day");
        return { start, end };
    }

    if (scale === "year") {
        const { jy } = gregorianToJalali(date);
        start = jalaliMonthStart(jy, 1);
        end = jalaliMonthEnd(jy, 12);
        return { start, end };
    }

    if (scale === "month") {
        const { jy, jm } = gregorianToJalali(date);
        start = jalaliMonthStart(jy, jm);
        end = jalaliMonthEnd(jy, jm);
        if (monthOverflow) {
            const paddedStart = startOfWeekForCalendar(start, firstDayOfWeek);
            const paddedEnd = paddedStart.plus({ weeks: 6, days: -1 }).endOf("day");
            return { start: paddedStart, end: paddedEnd };
        }
        return { start: start.startOf("day"), end: end.endOf("day") };
    }

    // week
    start = startOfWeekForCalendar(date, firstDayOfWeek);
    end = start.plus({ days: 6 }).endOf("day");
    return { start, end };
}

/**
 * @param {luxon.DateTime} date
 * @param {"day"|"week"|"month"|"year"} scale
 * @param {"next"|"previous"} direction
 * @returns {luxon.DateTime}
 */
export function stepJalaliCalendarDate(date, scale, direction) {
    const delta = direction === "next" ? 1 : -1;
    if (scale === "day") {
        return date.plus({ days: delta }).startOf("day");
    }
    if (scale === "week") {
        return date.plus({ weeks: delta }).startOf("day");
    }
    if (scale === "year") {
        const { jy, jm, jd } = gregorianToJalali(date);
        const targetJy = jy + delta;
        const targetJd = Math.min(jd, jalaliMonthLength(targetJy, jm));
        return jalaliToGregorian(targetJy, jm, targetJd).startOf("day");
    }
    // month — keep day-of-month when possible (clamp to target month length)
    const { jy, jm, jd } = gregorianToJalali(date);
    const next = addJalaliMonths(jy, jm, delta);
    const targetJd = Math.min(jd, jalaliMonthLength(next.jy, next.jm));
    return jalaliToGregorian(next.jy, next.jm, targetJd).startOf("day");
}

/**
 * @param {luxon.DateTime} date
 * @returns {string}
 */
export function formatJalaliMonthYear(date) {
    return formatJalali(date, "%B %Y");
}

/**
 * @param {luxon.DateTime} date
 * @returns {string}
 */
export function formatJalaliDayHeader(date) {
    return formatJalali(date, "%-d %B %Y");
}

/**
 * Week / mobile title spanning a range.
 *
 * @param {luxon.DateTime} rangeStart
 * @param {luxon.DateTime} rangeEnd
 * @returns {string}
 */
export function formatJalaliWeekHeader(rangeStart, rangeEnd) {
    const startJ = gregorianToJalali(rangeStart);
    const endJ = gregorianToJalali(rangeEnd);
    const months = getJalaliMonthNames();
    if (startJ.jy !== endJ.jy) {
        return `${months[startJ.jm - 1]} ${startJ.jy} - ${months[endJ.jm - 1]} ${endJ.jy}`;
    }
    if (startJ.jm !== endJ.jm) {
        return `${months[startJ.jm - 1]} - ${months[endJ.jm - 1]} ${startJ.jy}`;
    }
    return `${months[startJ.jm - 1]} ${startJ.jy}`;
}

/**
 * Mobile control-panel suffix for week/month.
 *
 * @param {luxon.DateTime} date
 * @param {"week"|"month"} scale
 * @param {luxon.DateTime} [rangeEnd]
 * @returns {string}
 */
export function formatJalaliCurrentDateSuffix(date, scale, rangeEnd) {
    if (scale === "week") {
        const end = rangeEnd || date.plus({ days: 6 });
        const startJ = gregorianToJalali(date);
        const endJ = gregorianToJalali(end);
        const short = getJalaliMonthNamesShort();
        let text;
        if (startJ.jm !== endJ.jm) {
            text = `${short[startJ.jm - 1]}-${short[endJ.jm - 1]}`;
        } else {
            text = getJalaliMonthNames()[startJ.jm - 1];
        }
        return ` - ${text} ${startJ.jy}`;
    }
    return ` - ${formatJalali(date, "%B %Y")}`;
}

/**
 * Whether a Gregorian date falls outside the focused Jalali month.
 *
 * @param {luxon.DateTime} cellDate
 * @param {luxon.DateTime} focusDate
 * @returns {boolean}
 */
export function isOutsideJalaliMonth(cellDate, focusDate) {
    const cell = gregorianToJalali(cellDate);
    const focus = gregorianToJalali(focusDate);
    return cell.jy !== focus.jy || cell.jm !== focus.jm;
}

/**
 * FullCalendar visibleRange for the current model range (end exclusive).
 *
 * @param {luxon.DateTime} rangeStart
 * @param {luxon.DateTime} rangeEnd
 * @returns {{ start: string, end: string }}
 */
export function toFullCalendarVisibleRange(rangeStart, rangeEnd) {
    return {
        start: rangeStart.toISODate(),
        end: rangeEnd.plus({ days: 1 }).toISODate(),
    };
}

/**
 * Props for CalendarCommonRendererHeader with Jalali day number.
 *
 * @param {Date} jsDate
 * @param {"day"|"week"|"month"|"year"} scale
 * @returns {object}
 */
export function jalaliHeaderTemplateProps(jsDate, scale) {
    const options = scale === "month" ? { zone: "UTC" } : {};
    const dt = DateTime.fromJSDate(jsDate, options);
    const { weekdayShort, weekdayLong } = dt;
    const { jd } = gregorianToJalali(dt);
    return {
        weekdayShort,
        weekdayLong,
        day: jd,
        scale,
    };
}

/**
 * @param {Date} jsDate
 * @param {"day"|"week"|"month"|"year"} scale
 * @returns {number} Jalali day of month
 */
export function jalaliDayNumberFromJsDate(jsDate, scale) {
    const options = scale === "month" ? { zone: "UTC" } : {};
    return gregorianToJalali(DateTime.fromJSDate(jsDate, options)).jd;
}

/**
 * First day of the Jalali year containing `date`.
 *
 * @param {luxon.DateTime} date
 * @returns {number}
 */
export function jalaliYearOf(date) {
    return gregorianToJalali(date).jy;
}

/**
 * @param {luxon.DateTime} date
 * @param {number} jm 1-12
 * @returns {luxon.DateTime}
 */
export function jalaliMonthAnchor(date, jm) {
    const { jy } = gregorianToJalali(date);
    return jalaliMonthStart(jy, jm);
}
