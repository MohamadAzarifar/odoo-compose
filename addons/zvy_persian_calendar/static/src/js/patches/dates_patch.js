/** @odoo-module **/

import { localization } from "@web/core/l10n/localization";
import * as dates from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";
import { gregorianToJalali } from "@zvy_persian_calendar/js/jalali_core";
import { formatJalali, parseJalali } from "@zvy_persian_calendar/js/jalali_format";
import {
    luxonDateFormatToJalaliPattern,
    splitLuxonDateTimeFormat,
} from "@zvy_persian_calendar/js/jalali_luxon_format";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

const { DateTime } = luxon;

/**
 * @param {luxon.DateTime} value
 * @param {string} luxonDateFormat
 * @returns {string}
 */
function formatJalaliDatePart(value, luxonDateFormat) {
    const pattern = luxonDateFormatToJalaliPattern(luxonDateFormat);
    return formatJalali(value, pattern);
}

/**
 * @param {luxon.DateTime} value
 * @returns {string}
 */
function toLocaleJalaliDateString(value) {
    const todayJalali = gregorianToJalali(dates.today());
    const valueJalali = gregorianToJalali(value);
    let pattern = "%d %B";
    if (todayJalali.jy !== valueJalali.jy) {
        pattern += " %Y";
    }
    return formatJalali(value, pattern);
}

/**
 * @param {string} value
 * @param {string} [format]
 * @returns {luxon.DateTime | null}
 */
function tryParseJalaliDate(value, format) {
    const dateFormat = format || localization.dateFormat;
    return parseJalali(value, luxonDateFormatToJalaliPattern(dateFormat));
}

/**
 * @param {string} value
 * @param {string} format
 * @returns {luxon.DateTime | null}
 */
function tryParseJalaliDateTime(value, format) {
    const [dateFormat, timeFormat] = splitLuxonDateTimeFormat(format);
    const jalaliPattern = luxonDateFormatToJalaliPattern(dateFormat);
    let datePart = value.trim();
    let timePart = "";
    if (timeFormat) {
        const timeMatch = value.trim().match(/\s+(\d{1,2}:\d{2}(:\d{2})?(\s*[APap][Mm])?)\s*$/);
        if (timeMatch) {
            timePart = timeMatch[1].trim();
            datePart = value.trim().slice(0, value.trim().length - timeMatch[0].length).trim();
        }
    }
    const parsedDate = parseJalali(datePart, jalaliPattern);
    if (!parsedDate) {
        return null;
    }
    if (timePart) {
        const timeParsed = DateTime.fromFormat(timePart, timeFormat, {
            zone: "default",
        });
        if (timeParsed.isValid) {
            return parsedDate.set({
                hour: timeParsed.hour,
                minute: timeParsed.minute,
                second: timeParsed.second,
            });
        }
    }
    return parsedDate;
}

patch(dates, {
    formatDate(value, options = {}) {
        if (!isJalaliActive()) {
            return super.formatDate(...arguments);
        }
        if (!value) {
            return "";
        }
        const format = options.format || localization.dateFormat;
        return formatJalaliDatePart(value, format);
    },

    formatDateTime(value, options = {}) {
        if (!isJalaliActive()) {
            return super.formatDateTime(...arguments);
        }
        if (!value) {
            return "";
        }
        const format = options.format || localization.dateTimeFormat;
        const [dateFormat, timeFormat] = splitLuxonDateTimeFormat(format);
        let result = formatJalaliDatePart(value, dateFormat);
        if (timeFormat) {
            const time = value.setZone(options.tz || "default").toFormat(timeFormat);
            result = result ? `${result} ${time}` : time;
        }
        return result;
    },

    toLocaleDateString(value) {
        if (!isJalaliActive()) {
            return super.toLocaleDateString(...arguments);
        }
        if (!value) {
            return "";
        }
        return toLocaleJalaliDateString(value);
    },

    toLocaleDateTimeString(value, options = {}) {
        if (!isJalaliActive()) {
            return super.toLocaleDateTimeString(...arguments);
        }
        if (!value) {
            return "";
        }
        const showDate = options.showDate !== false;
        const showTime = options.showTime !== false;
        const parts = [];
        if (showDate) {
            parts.push(toLocaleJalaliDateString(value));
        }
        if (showTime) {
            let timeFormat = localization.timeFormat;
            if (options.showSeconds && !timeFormat.includes("ss")) {
                timeFormat = `${timeFormat}:ss`;
            }
            parts.push(value.setZone(options.tz || "default").toFormat(timeFormat));
        }
        return parts.join(", ");
    },

    parseDate(value, options = {}) {
        if (!isJalaliActive()) {
            return super.parseDate(...arguments);
        }
        if (!value) {
            return false;
        }
        const format = options.format || localization.dateFormat;
        const jalaliParsed = tryParseJalaliDate(value, format);
        if (jalaliParsed) {
            return jalaliParsed.startOf("day");
        }
        return super.parseDate(...arguments);
    },

    parseDateTime(value, options = {}) {
        if (!isJalaliActive()) {
            return super.parseDateTime(...arguments);
        }
        if (!value) {
            return false;
        }
        const format = options.format || localization.dateTimeFormat;
        const jalaliParsed = tryParseJalaliDateTime(value, format);
        if (jalaliParsed) {
            return jalaliParsed.setZone(options.tz || "default");
        }
        return super.parseDateTime(...arguments);
    },
});
