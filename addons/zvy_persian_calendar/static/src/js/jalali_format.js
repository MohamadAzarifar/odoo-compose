/** @odoo-module **/

import { gregorianToJalali, jalaliToGregorian } from "./jalali_core";

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const LATIN_DIGITS = "0123456789";

const PERSIAN_MONTHS = [
    "Farvardin",
    "Ordibehesht",
    "Khordad",
    "Tir",
    "Mordad",
    "Shahrivar",
    "Mehr",
    "Aban",
    "Azar",
    "Dey",
    "Bahman",
    "Esfand",
];

const PERSIAN_MONTHS_SHORT = PERSIAN_MONTHS.map((name) => name.slice(0, 3));

/**
 * @param {string} value
 * @returns {string}
 */
export function toPersianDigits(value) {
    return String(value).replace(/\d/g, (digit) => PERSIAN_DIGITS[Number(digit)]);
}

/**
 * @param {string} value
 * @returns {string}
 */
export function toLatinDigits(value) {
    return String(value).replace(/[۰-۹]/g, (digit) => {
        const index = PERSIAN_DIGITS.indexOf(digit);
        return index >= 0 ? LATIN_DIGITS[index] : digit;
    });
}

/**
 * @param {luxon.DateTime} date
 * @param {string} pattern
 * @returns {string}
 */
export function formatJalali(date, pattern = "%Y/%m/%d") {
    const { jy, jm, jd } = gregorianToJalali(date);
    const monthName = PERSIAN_MONTHS[jm - 1] || "";
    const monthShort = PERSIAN_MONTHS_SHORT[jm - 1] || "";
    const pad2 = (num) => String(num).padStart(2, "0");

    return pattern
        .replace(/%Y/g, String(jy))
        .replace(/%y/g, String(jy).slice(-2))
        .replace(/%m/g, pad2(jm))
        .replace(/%d/g, pad2(jd))
        .replace(/%B/g, monthName)
        .replace(/%b/g, monthShort)
        .replace(/%-m/g, String(jm))
        .replace(/%-d/g, String(jd));
}

/**
 * @param {string} value
 * @param {string} pattern
 * @returns {luxon.DateTime | null}
 */
export function parseJalali(value, pattern = "%Y/%m/%d") {
    if (!value) {
        return null;
    }
    const normalized = toLatinDigits(value.trim());
    const tokenRegex = /%[YymdBd]|%-[md]/g;
    const tokens = pattern.match(tokenRegex) || [];
    let regexPattern = pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const captureGroups = [];

    for (const token of tokens) {
        switch (token) {
            case "%Y":
                regexPattern = regexPattern.replace("%Y", "(\\d{4})");
                captureGroups.push("Y");
                break;
            case "%y":
                regexPattern = regexPattern.replace("%y", "(\\d{2})");
                captureGroups.push("y");
                break;
            case "%m":
                regexPattern = regexPattern.replace("%m", "(\\d{2})");
                captureGroups.push("m");
                break;
            case "%-m":
                regexPattern = regexPattern.replace("%-m", "(\\d{1,2})");
                captureGroups.push("m");
                break;
            case "%d":
                regexPattern = regexPattern.replace("%d", "(\\d{2})");
                captureGroups.push("d");
                break;
            case "%-d":
                regexPattern = regexPattern.replace("%-d", "(\\d{1,2})");
                captureGroups.push("d");
                break;
            case "%B":
                regexPattern = regexPattern.replace(
                    "%B",
                    `(${PERSIAN_MONTHS.join("|")})`
                );
                captureGroups.push("B");
                break;
            case "%b":
                regexPattern = regexPattern.replace(
                    "%b",
                    `(${PERSIAN_MONTHS_SHORT.join("|")})`
                );
                captureGroups.push("b");
                break;
        }
    }

    const match = normalized.match(new RegExp(`^${regexPattern}$`));
    if (!match) {
        return null;
    }

    let jy;
    let jm;
    let jd;
    for (let index = 0; index < captureGroups.length; index++) {
        const token = captureGroups[index];
        const part = match[index + 1];
        switch (token) {
            case "Y":
                jy = Number(part);
                break;
            case "y":
                jy = 1300 + Number(part);
                break;
            case "m":
                jm = Number(part);
                break;
            case "d":
                jd = Number(part);
                break;
            case "B":
                jm = PERSIAN_MONTHS.indexOf(part) + 1;
                break;
            case "b":
                jm = PERSIAN_MONTHS_SHORT.indexOf(part) + 1;
                break;
        }
    }

    if (!jy || !jm || !jd) {
        return null;
    }
    try {
        return jalaliToGregorian(jy, jm, jd);
    } catch {
        return null;
    }
}
