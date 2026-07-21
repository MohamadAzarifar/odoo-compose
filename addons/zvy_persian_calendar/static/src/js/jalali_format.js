/** @odoo-module **/

import { localization } from "@web/core/l10n/localization";
import { user } from "@web/core/user";
import { session } from "@web/session";
import { gregorianToJalali, jalaliToGregorian } from "./jalali_core";

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const LATIN_DIGITS = "0123456789";

/** Latin transliterations (used when UI language is not Persian). */
export const JALALI_MONTHS_EN = [
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

/** Native Persian month names (used when UI language is Persian). */
export const JALALI_MONTHS_FA = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
];

/** @deprecated use getJalaliMonthNames() or JALALI_MONTHS_EN / JALALI_MONTHS_FA */
export const PERSIAN_MONTHS = JALALI_MONTHS_EN;

/**
 * Current UI language code (e.g. "fa-IR", "fa_IR", "en-US").
 * Odoo 19 removes session.user_context after boot; use user.lang instead.
 * @returns {string}
 */
export function getUiLanguage() {
    return (
        user.lang ||
        localization.code ||
        session.user_context?.lang ||
        document.documentElement.getAttribute("lang") ||
        ""
    );
}

/**
 * @param {string} [lang]
 * @returns {boolean}
 */
export function isPersianUiLanguage(lang) {
    const code = (lang || getUiLanguage()).toLowerCase();
    return code.startsWith("fa");
}

/**
 * @param {string} [lang]
 * @returns {string[]}
 */
export function getJalaliMonthNames(lang) {
    return isPersianUiLanguage(lang) ? JALALI_MONTHS_FA : JALALI_MONTHS_EN;
}

/**
 * @param {string} [lang]
 * @returns {string[]}
 */
export function getJalaliMonthNamesShort(lang) {
    return getJalaliMonthNames(lang).map((name) => name.slice(0, 3));
}

/**
 * All month names accepted by the parser (Latin + فارسی).
 * @returns {string[]}
 */
function getAllMonthNames() {
    return [...JALALI_MONTHS_EN, ...JALALI_MONTHS_FA];
}

/**
 * @returns {string[]}
 */
function getAllMonthNamesShort() {
    return getAllMonthNames().map((name) => name.slice(0, 3));
}

/**
 * @param {string} name
 * @returns {number} 1-12, or 0 if unknown
 */
function monthIndexFromName(name) {
    const enIndex = JALALI_MONTHS_EN.indexOf(name);
    if (enIndex >= 0) {
        return enIndex + 1;
    }
    const faIndex = JALALI_MONTHS_FA.indexOf(name);
    if (faIndex >= 0) {
        return faIndex + 1;
    }
    // Short forms
    const shortEn = JALALI_MONTHS_EN.map((n) => n.slice(0, 3));
    const shortFa = JALALI_MONTHS_FA.map((n) => n.slice(0, 3));
    const shortEnIndex = shortEn.indexOf(name);
    if (shortEnIndex >= 0) {
        return shortEnIndex + 1;
    }
    const shortFaIndex = shortFa.indexOf(name);
    if (shortFaIndex >= 0) {
        return shortFaIndex + 1;
    }
    return 0;
}

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
    const months = getJalaliMonthNames();
    const monthsShort = getJalaliMonthNamesShort();
    const monthName = months[jm - 1] || "";
    const monthShort = monthsShort[jm - 1] || "";
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
 * Escape a string for use inside a RegExp character class / alternation.
 * @param {string} value
 * @returns {string}
 */
function escapeRegExp(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
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
            case "%B": {
                const names = getAllMonthNames().map(escapeRegExp).join("|");
                regexPattern = regexPattern.replace("%B", `(${names})`);
                captureGroups.push("B");
                break;
            }
            case "%b": {
                // Prefer longer names first so "Ord" doesn't steal from full names when mixed.
                const names = getAllMonthNamesShort().map(escapeRegExp).join("|");
                regexPattern = regexPattern.replace("%b", `(${names})`);
                captureGroups.push("b");
                break;
            }
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
            case "b":
                jm = monthIndexFromName(part);
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
