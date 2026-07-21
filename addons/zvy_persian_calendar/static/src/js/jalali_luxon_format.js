/** @odoo-module **/

/**
 * Convert a Luxon date-format string to a jalali_format pattern.
 * Literal segments (single-quoted) are copied unchanged.
 *
 * @param {string} luxonFormat
 * @returns {string}
 */
export function luxonDateFormatToJalaliPattern(luxonFormat) {
    let result = "";
    let index = 0;
    while (index < luxonFormat.length) {
        const char = luxonFormat[index];
        if (char === "'") {
            let end = index + 1;
            while (end < luxonFormat.length && luxonFormat[end] !== "'") {
                end++;
            }
            result += luxonFormat.slice(index, end + 1);
            index = end + 1;
            continue;
        }
        const rest = luxonFormat.slice(index);
        if (rest.startsWith("yyyy")) {
            result += "%Y";
            index += 4;
        } else if (rest.startsWith("yy")) {
            result += "%y";
            index += 2;
        } else if (rest.startsWith("MMMM")) {
            result += "%B";
            index += 4;
        } else if (rest.startsWith("MMM")) {
            result += "%b";
            index += 3;
        } else if (rest.startsWith("MM")) {
            result += "%m";
            index += 2;
        } else if (rest.startsWith("dd")) {
            result += "%d";
            index += 2;
        } else if (char === "M") {
            result += "%-m";
            index += 1;
        } else if (char === "d") {
            result += "%-d";
            index += 1;
        } else {
            result += char;
            index += 1;
        }
    }
    return result;
}

/**
 * Split a Luxon datetime format into date and time portions.
 *
 * @param {string} format
 * @returns {[string, string]}
 */
export function splitLuxonDateTimeFormat(format) {
    const timeTokenStart = format.search(/H{1,2}|h{1,2}|m{1,2}|s{1,2}|S{1,3}|a|A/);
    if (timeTokenStart === -1) {
        return [format, ""];
    }
    let splitAt = timeTokenStart;
    while (splitAt > 0 && /[\s,]/.test(format[splitAt - 1])) {
        splitAt--;
    }
    return [format.slice(0, splitAt).trimEnd(), format.slice(splitAt).trimStart()];
}
