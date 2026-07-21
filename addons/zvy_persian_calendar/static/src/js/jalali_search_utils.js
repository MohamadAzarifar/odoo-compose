/** @odoo-module **/

import { Domain } from "@web/core/domain";
import { serializeDate, serializeDateTime } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { clamp } from "@web/core/utils/numbers";
import { pick } from "@web/core/utils/objects";

import { gregorianToJalali } from "./jalali_core";
import {
    getJalaliMonthNames,
    isPersianUiLanguage,
    toPersianDigits,
} from "./jalali_format";
import {
    addJalaliMonths,
    jalaliMonthEnd,
    jalaliMonthStart,
} from "./jalali_picker_utils";

/**
 * Jalali calendar quarters (not Gregorian fiscal quarters).
 * Q1 Farvardin–Khordad … Q4 Dey–Esfand.
 *
 * Labels are owned here (not `_t("Q1")`…): Odoo’s `fa.po` only translates Q1 → س۱,
 * leaving Q2–Q4 as English.
 */
export const JALALI_QUARTERS = {
    1: { coveredMonths: [1, 2, 3] },
    2: { coveredMonths: [4, 5, 6] },
    3: { coveredMonths: [7, 8, 9] },
    4: { coveredMonths: [10, 11, 12] },
};

/**
 * @param {number} quarter 1..4
 * @param {string} [lang]
 * @returns {string}
 */
export function getJalaliQuarterLabel(quarter, lang) {
    if (isPersianUiLanguage(lang)) {
        return toPersianDigits(`س${quarter}`);
    }
    return `Q${quarter}`;
}

const QUARTER_OPTION_IDS = {
    first_quarter: 1,
    second_quarter: 2,
    third_quarter: 3,
    fourth_quarter: 4,
};

/**
 * @param {string} unit
 * @param {number} [offset]
 * @returns {string}
 */
export function toGeneratorId(unit, offset) {
    if (!offset) {
        return unit;
    }
    const sep = offset > 0 ? "+" : "-";
    const val = Math.abs(offset);
    return `${unit}${sep}${val}`;
}

/**
 * @param {luxon.DateTime} referenceMoment
 * @param {number} monthOffset
 * @returns {{ jy: number, jm: number }}
 */
export function jalaliMonthAtOffset(referenceMoment, monthOffset) {
    const { jy, jm } = gregorianToJalali(referenceMoment);
    return addJalaliMonths(jy, jm, monthOffset);
}

/**
 * @param {luxon.DateTime} referenceMoment
 * @param {number} yearOffset
 * @returns {number}
 */
export function jalaliYearAtOffset(referenceMoment, yearOffset) {
    return gregorianToJalali(referenceMoment).jy + yearOffset;
}

/**
 * @param {number} jy
 * @param {number} jm
 * @returns {{ left: luxon.DateTime, right: luxon.DateTime }}
 */
export function jalaliMonthBounds(jy, jm) {
    return {
        left: jalaliMonthStart(jy, jm),
        right: jalaliMonthEnd(jy, jm),
    };
}

/**
 * @param {number} jy
 * @returns {{ left: luxon.DateTime, right: luxon.DateTime }}
 */
export function jalaliYearBounds(jy) {
    return {
        left: jalaliMonthStart(jy, 1),
        right: jalaliMonthEnd(jy, 12),
    };
}

/**
 * @param {number} jy
 * @param {number} quarter 1..4
 * @returns {{ left: luxon.DateTime, right: luxon.DateTime }}
 */
export function jalaliQuarterBounds(jy, quarter) {
    const months = JALALI_QUARTERS[quarter].coveredMonths;
    return {
        left: jalaliMonthStart(jy, months[0]),
        right: jalaliMonthEnd(jy, months[months.length - 1]),
    };
}

/**
 * Period menu options with Jalali month names and Jalali year labels.
 * Option ids stay compatible with stock SearchModel (`month`, `year`, quarters).
 *
 * @param {luxon.DateTime} referenceMoment
 * @param {object} optionsParams
 * @returns {object[]}
 */
export function getJalaliPeriodOptions(referenceMoment, optionsParams) {
    return [
        ...getJalaliMonthPeriodOptions(referenceMoment, optionsParams),
        ...getJalaliQuarterPeriodOptions(optionsParams),
        ...getJalaliYearPeriodOptions(referenceMoment, optionsParams),
        ...getCustomPeriodOptions(optionsParams),
    ];
}

/**
 * @param {luxon.DateTime} referenceMoment
 * @param {object} searchItem
 * @param {string[]} selectedOptionIds
 * @returns {{ domain: Domain, description: string }}
 */
export function constructJalaliDateDomain(referenceMoment, searchItem, selectedOptionIds) {
    if (!selectedOptionIds?.length) {
        return { domain: new Domain(`[]`), description: "" };
    }
    const selectedOptions = getJalaliSelectedOptions(
        referenceMoment,
        searchItem,
        selectedOptionIds
    );
    if ("withDomain" in selectedOptions) {
        return {
            description: selectedOptions.withDomain[0].description,
            domain: Domain.and([selectedOptions.withDomain[0].domain, searchItem.domain]),
        };
    }
    const yearOptions = selectedOptions.year || [];
    const otherOptions = [...(selectedOptions.quarter || []), ...(selectedOptions.month || [])];
    sortJalaliPeriodOptions(yearOptions);
    sortJalaliPeriodOptions(otherOptions);
    const ranges = [];
    const { fieldName, fieldType } = searchItem;
    for (const yearOption of yearOptions) {
        const jy = yearOption.jy;
        if (otherOptions.length) {
            for (const option of otherOptions) {
                ranges.push(
                    constructJalaliDateRange({
                        fieldName,
                        fieldType,
                        jy,
                        jm: option.jm,
                        quarter: option.quarter,
                        granularity: option.granularity,
                    })
                );
            }
        } else {
            ranges.push(
                constructJalaliDateRange({
                    fieldName,
                    fieldType,
                    jy,
                    granularity: "year",
                })
            );
        }
    }
    if (!ranges.length) {
        return { domain: new Domain(`[]`), description: "" };
    }
    let domain = Domain.combine(
        ranges.map((range) => range.domain),
        "OR"
    );
    domain = Domain.and([domain, searchItem.domain]);
    const description = ranges.map((range) => range.description).join("/");
    return { domain, description };
}

/**
 * Smart-date bounds for domain-selector "in range".
 * Returns half-open [left, rightExclusive) as Gregorian ISO strings (stock shape).
 * Day-based presets (today / last N days) return null → keep stock relative strings.
 *
 * @param {luxon.DateTime} referenceMoment
 * @param {"date"|"datetime"} fieldType
 * @param {string} valueType
 * @returns {[string, string]|null}
 */
export function getJalaliSmartDateBounds(referenceMoment, fieldType, valueType) {
    const todayDt = referenceMoment.startOf("day");
    const { jy, jm } = gregorianToJalali(todayDt);
    let left;
    let rightExclusive;

    switch (valueType) {
        case "month to date": {
            left = jalaliMonthStart(jy, jm);
            rightExclusive = todayDt.plus({ days: 1 }).startOf("day");
            break;
        }
        case "last month": {
            const prev = addJalaliMonths(jy, jm, -1);
            left = jalaliMonthStart(prev.jy, prev.jm);
            rightExclusive = jalaliMonthStart(jy, jm);
            break;
        }
        case "year to date": {
            left = jalaliMonthStart(jy, 1);
            rightExclusive = todayDt.plus({ days: 1 }).startOf("day");
            break;
        }
        case "last 12 months": {
            const start = addJalaliMonths(jy, jm, -12);
            left = jalaliMonthStart(start.jy, start.jm);
            rightExclusive = jalaliMonthStart(jy, jm);
            break;
        }
        default:
            return null;
    }

    if (fieldType === "date") {
        return [serializeDate(left), serializeDate(rightExclusive)];
    }
    return [
        serializeDateTime(left.startOf("day")),
        serializeDateTime(rightExclusive.startOf("day")),
    ];
}

/**
 * Note for docs: Iranian fiscal year often starts 1 Farvardin (same as Jalali
 * calendar year), but company fiscal calendars may differ — Filters “This year”
 * always means the current Jalali calendar year, not necessarily fiscal year.
 */

// -------------------------------------------------------------------------
// Internals
// -------------------------------------------------------------------------

function getJalaliMonthPeriodOptions(referenceMoment, optionsParams) {
    const { startYear, endYear, startMonth, endMonth } = optionsParams;
    const { jy: refJy } = gregorianToJalali(referenceMoment);
    const monthNames = getJalaliMonthNames();
    return [...Array(endMonth - startMonth + 1).keys()]
        .map((i) => {
            const monthOffset = startMonth + i;
            const { jy, jm } = jalaliMonthAtOffset(referenceMoment, monthOffset);
            const yearOffset = jy - refJy;
            return {
                id: toGeneratorId("month", monthOffset),
                defaultYearId: toGeneratorId("year", clamp(yearOffset, startYear, endYear)),
                description: monthNames[jm - 1],
                granularity: "month",
                groupNumber: 1,
                plusParam: { months: monthOffset },
                jy,
                jm,
            };
        })
        .reverse();
}

function getJalaliQuarterPeriodOptions(optionsParams) {
    const { startYear, endYear } = optionsParams;
    const defaultYearId = toGeneratorId("year", clamp(0, startYear, endYear));
    return [
        {
            id: "fourth_quarter",
            groupNumber: 1,
            description: getJalaliQuarterLabel(4),
            setParam: { quarter: 4 },
            granularity: "quarter",
            defaultYearId,
            quarter: 4,
        },
        {
            id: "third_quarter",
            groupNumber: 1,
            description: getJalaliQuarterLabel(3),
            setParam: { quarter: 3 },
            granularity: "quarter",
            defaultYearId,
            quarter: 3,
        },
        {
            id: "second_quarter",
            groupNumber: 1,
            description: getJalaliQuarterLabel(2),
            setParam: { quarter: 2 },
            granularity: "quarter",
            defaultYearId,
            quarter: 2,
        },
        {
            id: "first_quarter",
            groupNumber: 1,
            description: getJalaliQuarterLabel(1),
            setParam: { quarter: 1 },
            granularity: "quarter",
            defaultYearId,
            quarter: 1,
        },
    ];
}

function getJalaliYearPeriodOptions(referenceMoment, optionsParams) {
    const { startYear, endYear } = optionsParams;
    return [...Array(endYear - startYear + 1).keys()]
        .map((i) => {
            const offset = startYear + i;
            const jy = jalaliYearAtOffset(referenceMoment, offset);
            return {
                id: toGeneratorId("year", offset),
                description: String(jy),
                granularity: "year",
                groupNumber: 2,
                plusParam: { years: offset },
                jy,
            };
        })
        .reverse();
}

function getCustomPeriodOptions(optionsParams) {
    const { customOptions } = optionsParams;
    return (customOptions || []).map((option) => ({
        id: option.id,
        description: option.description,
        granularity: "withDomain",
        groupNumber: 3,
        domain: option.domain,
    }));
}

function getJalaliSelectedOptions(referenceMoment, searchItem, selectedOptionIds) {
    const selectedOptions = { year: [] };
    const periodOptions = getJalaliPeriodOptions(referenceMoment, searchItem.optionsParams);
    for (const optionId of selectedOptionIds) {
        const option = periodOptions.find((o) => o.id === optionId);
        if (!option) {
            continue;
        }
        const granularity = option.granularity;
        if (!selectedOptions[granularity]) {
            selectedOptions[granularity] = [];
        }
        if (option.domain) {
            selectedOptions[granularity].push(pick(option, "domain", "description"));
        } else if (granularity === "year") {
            selectedOptions.year.push({
                granularity: "year",
                jy: option.jy ?? jalaliYearAtOffset(referenceMoment, option.plusParam?.years || 0),
            });
        } else if (granularity === "month") {
            const { jy, jm } =
                option.jy !== undefined
                    ? { jy: option.jy, jm: option.jm }
                    : jalaliMonthAtOffset(referenceMoment, option.plusParam?.months || 0);
            selectedOptions.month.push({ granularity: "month", jy, jm });
        } else if (granularity === "quarter") {
            const quarter = option.quarter ?? QUARTER_OPTION_IDS[optionId] ?? option.setParam?.quarter;
            selectedOptions.quarter.push({ granularity: "quarter", quarter });
        }
    }
    return selectedOptions;
}

function constructJalaliDateRange({ fieldName, fieldType, jy, jm, quarter, granularity }) {
    let leftDate;
    let rightDate;
    const descriptions = [String(jy)];
    const method = localization.direction === "rtl" ? "push" : "unshift";

    if (granularity === "year") {
        ({ left: leftDate, right: rightDate } = jalaliYearBounds(jy));
    } else if (granularity === "month") {
        ({ left: leftDate, right: rightDate } = jalaliMonthBounds(jy, jm));
        descriptions[method](getJalaliMonthNames()[jm - 1]);
    } else if (granularity === "quarter") {
        ({ left: leftDate, right: rightDate } = jalaliQuarterBounds(jy, quarter));
        descriptions[method](getJalaliQuarterLabel(quarter));
    }

    let leftBound;
    let rightBound;
    if (fieldType === "date") {
        leftBound = serializeDate(leftDate);
        rightBound = serializeDate(rightDate);
    } else {
        leftBound = serializeDateTime(leftDate.startOf("day"));
        rightBound = serializeDateTime(rightDate.endOf("day"));
    }
    const domain = new Domain(["&", [fieldName, ">=", leftBound], [fieldName, "<=", rightBound]]);
    return { domain, description: descriptions.join(" ") };
}

function sortJalaliPeriodOptions(options) {
    options.sort((o1, o2) => {
        const g1 = o1.granularity;
        const g2 = o2.granularity;
        if (g1 === g2) {
            if (g1 === "year") {
                return (o1.jy ?? 0) - (o2.jy ?? 0);
            }
            if (g1 === "month") {
                return (o1.jm ?? 0) - (o2.jm ?? 0);
            }
            if (g1 === "quarter") {
                return (o1.quarter ?? 0) - (o2.quarter ?? 0);
            }
            return 0;
        }
        return g1 < g2 ? -1 : 1;
    });
}
