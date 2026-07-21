/** @odoo-module **/

import { isInRange, today } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { _t } from "@web/core/l10n/translation";
import { gregorianToJalali, jalaliMonthLength, jalaliToGregorian } from "./jalali_core";
import { formatJalali, getJalaliMonthNames, getJalaliMonthNamesShort } from "./jalali_format";

const { Info } = luxon;

const DAYS_PER_WEEK = 7;
const WEEKS_PER_MONTH = 6;
const GRID_COUNT = 10;
const GRID_MARGIN = 1;

/**
 * @param {number} jy
 * @param {number} jm
 * @param {number} delta
 * @returns {{ jy: number, jm: number }}
 */
export function addJalaliMonths(jy, jm, delta) {
    const totalMonths = jy * 12 + (jm - 1) + delta;
    return {
        jy: Math.floor(totalMonths / 12),
        jm: (totalMonths % 12) + 1,
    };
}

/**
 * @param {number} jy
 * @param {number} jm
 * @returns {luxon.DateTime}
 */
export function jalaliMonthStart(jy, jm) {
    return jalaliToGregorian(jy, jm, 1).startOf("day");
}

/**
 * @param {number} jy
 * @param {number} jm
 * @returns {luxon.DateTime}
 */
export function jalaliMonthEnd(jy, jm) {
    return jalaliToGregorian(jy, jm, jalaliMonthLength(jy, jm)).endOf("day");
}

/**
 * @param {luxon.DateTime} date
 * @returns {string}
 */
export function getJalaliMonthTitle(date) {
    return formatJalali(date, "%B %Y");
}

/**
 * @param {luxon.DateTime} date
 * @returns {luxon.DateTime}
 */
function getStartOfWeek(date) {
    const { weekStart } = localization;
    return date.set({ weekday: date.weekday < weekStart ? weekStart - 7 : weekStart });
}

/**
 * @param {object} params
 * @returns {object}
 */
function toDateItem({ isOutOfRange = false, isValid = true, label, range, extraClass }) {
    const todayJalali = gregorianToJalali(today());
    const dayJalali = gregorianToJalali(range[0]);
    return {
        id: range[0].toISODate(),
        includesToday:
            todayJalali.jy === dayJalali.jy &&
            todayJalali.jm === dayJalali.jm &&
            todayJalali.jd === dayJalali.jd,
        isOutOfRange,
        isValid,
        label: String(label),
        range,
        extraClass: extraClass || "",
    };
}

/**
 * @param {luxon.DateTime} focusDate
 * @param {object} params
 * @returns {object[]}
 */
export function buildJalaliDaysItems(
    focusDate,
    { maxDate, minDate, showWeekNumbers, isDateValid, dayCellClass }
) {
    const { jy, jm } = gregorianToJalali(focusDate);
    const monthStart = jalaliMonthStart(jy, jm);
    const weeks = [];
    let startOfNextWeek = getStartOfWeek(monthStart);

    for (let w = 0; w < WEEKS_PER_MONTH; w++) {
        const weekDayItems = [];
        for (let d = 0; d < DAYS_PER_WEEK; d++) {
            const day = startOfNextWeek.plus({ days: d });
            const range = [day.startOf("day"), day.endOf("day")];
            const dayJalali = gregorianToJalali(day);
            weekDayItems.push(
                toDateItem({
                    isOutOfRange: dayJalali.jy !== jy || dayJalali.jm !== jm,
                    isValid:
                        isInRange(range, [minDate, maxDate]) &&
                        (!isDateValid || isDateValid(day)),
                    label: dayJalali.jd,
                    range,
                    extraClass: dayCellClass?.(day) || "",
                })
            );
            if (d === DAYS_PER_WEEK - 1) {
                startOfNextWeek = day.plus({ days: 1 });
            }
        }
        weeks.push({
            number: weekDayItems[3].range[0].weekNumber,
            days: weekDayItems,
        });
    }

    const daysOfWeek = weeks[0].days.map((d) => [
        d.range[0].weekdayShort,
        d.range[0].weekdayLong,
        Info.weekdays("narrow", { locale: d.range[0].locale })[d.range[0].weekday - 1],
    ]);
    if (showWeekNumbers) {
        daysOfWeek.unshift(["", _t("Week numbers"), ""]);
    }

    return [
        {
            id: "__month__0",
            number: jm,
            daysOfWeek,
            weeks,
        },
    ];
}

/**
 * @param {luxon.DateTime} focusDate
 * @param {object} params
 * @returns {object[]}
 */
export function buildJalaliMonthsItems(focusDate, { maxDate, minDate }) {
    const { jy } = gregorianToJalali(focusDate);
    const shortNames = getJalaliMonthNamesShort();
    return getJalaliMonthNames().map((monthName, index) => {
        const jm = index + 1;
        const range = [jalaliMonthStart(jy, jm), jalaliMonthEnd(jy, jm)];
        return toDateItem({
            isValid: isInRange(range, [minDate, maxDate]),
            label: shortNames[index] || monthName,
            range,
        });
    });
}

/**
 * @param {luxon.DateTime} focusDate
 * @param {object} params
 * @returns {object[]}
 */
export function buildJalaliYearsItems(focusDate, { maxDate, minDate }) {
    const { jy } = gregorianToJalali(focusDate);
    const startDecade = Math.floor(jy / 10) * 10;
    return [...Array(GRID_COUNT + 2 * GRID_MARGIN)].map((_, index) => {
        const offset = index - GRID_MARGIN;
        const year = startDecade + offset;
        const range = [jalaliMonthStart(year, 1), jalaliMonthEnd(year, 12)];
        return toDateItem({
            isOutOfRange: offset < 0 || offset >= GRID_COUNT,
            isValid: isInRange(range, [minDate, maxDate]),
            label: year,
            range,
        });
    });
}

/**
 * @param {luxon.DateTime} focusDate
 * @param {object} params
 * @returns {object[]}
 */
export function buildJalaliDecadesItems(focusDate, { maxDate, minDate }) {
    const { jy } = gregorianToJalali(focusDate);
    const startCentury = Math.floor(jy / 100) * 100;
    return [...Array(GRID_COUNT + 2 * GRID_MARGIN)].map((_, index) => {
        const offset = index - GRID_MARGIN;
        const decadeStart = startCentury + offset * 10;
        const range = [jalaliMonthStart(decadeStart, 1), jalaliMonthEnd(decadeStart + 9, 12)];
        return toDateItem({
            isOutOfRange: offset < 0 || offset >= GRID_COUNT,
            isValid: isInRange(range, [minDate, maxDate]),
            label: `${decadeStart}`,
            range,
        });
    });
}

/**
 * @param {luxon.DateTime} focusDate
 * @param {string} precision
 * @returns {string}
 */
export function getJalaliPrecisionTitle(focusDate, precision) {
    const { jy } = gregorianToJalali(focusDate);
    switch (precision) {
        case "days":
            return getJalaliMonthTitle(focusDate);
        case "months":
            return String(jy);
        case "years": {
            const startDecade = Math.floor(jy / 10) * 10;
            return `${startDecade - 1} - ${startDecade + 10}`;
        }
        case "decades": {
            const startCentury = Math.floor(jy / 100) * 100;
            return `${startCentury - 10} - ${startCentury + 100}`;
        }
        default:
            return getJalaliMonthTitle(focusDate);
    }
}

/**
 * @param {luxon.DateTime} focusDate
 * @param {string} precision
 * @param {object} params
 * @returns {object[]}
 */
export function buildJalaliPrecisionItems(focusDate, precision, params) {
    switch (precision) {
        case "days":
            return buildJalaliDaysItems(focusDate, params);
        case "months":
            return buildJalaliMonthsItems(focusDate, params);
        case "years":
            return buildJalaliYearsItems(focusDate, params);
        case "decades":
            return buildJalaliDecadesItems(focusDate, params);
        default:
            return buildJalaliDaysItems(focusDate, params);
    }
}

/**
 * @param {luxon.DateTime} focusDate
 * @param {string} precision
 * @param {"next" | "previous"} direction
 * @returns {luxon.DateTime}
 */
export function stepJalaliFocusDate(focusDate, precision, direction) {
    const { jy, jm } = gregorianToJalali(focusDate);
    const delta = direction === "next" ? 1 : -1;
    switch (precision) {
        case "days": {
            const next = addJalaliMonths(jy, jm, delta);
            return jalaliMonthStart(next.jy, next.jm);
        }
        case "months":
            return jalaliMonthStart(jy + delta, jm);
        case "years":
            return jalaliMonthStart(jy + delta * 10, jm);
        case "decades":
            return jalaliMonthStart(jy + delta * 100, jm);
        default:
            return focusDate;
    }
}

/**
 * @param {luxon.DateTime} dateToFocus
 * @returns {luxon.DateTime}
 */
export function adjustJalaliFocus(dateToFocus) {
    const { jy, jm } = gregorianToJalali(dateToFocus);
    return jalaliMonthStart(jy, jm);
}

/**
 * @param {"date" | "datetime"} type
 * @returns {string}
 */
export function getJalaliInputPlaceholder(type) {
    const sample = jalaliToGregorian(1403, 7, 21);
    const datePart = formatJalali(sample, "%Y/%m/%d");
    return type === "datetime" ? `${datePart} 14:30` : datePart;
}
