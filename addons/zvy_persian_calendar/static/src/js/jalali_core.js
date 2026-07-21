/** @odoo-module **/

import {
    isLeapJalaaliYear,
    isValidJalaaliDate,
    jalaaliMonthLength,
    toGregorian,
    toJalaali,
} from "../../lib/jalaali/jalaali";

const { DateTime } = luxon;

/**
 * @param {luxon.DateTime} date
 * @returns {{ jy: number, jm: number, jd: number }}
 */
export function gregorianToJalali(date) {
    return toJalaali(date.year, date.month, date.day);
}

/**
 * @param {number} jy
 * @param {number} jm
 * @param {number} jd
 * @returns {luxon.DateTime}
 */
export function jalaliToGregorian(jy, jm, jd) {
    const { gy, gm, gd } = toGregorian(jy, jm, jd);
    return DateTime.fromObject({ year: gy, month: gm, day: gd });
}

/**
 * @param {number} jy
 * @param {number} jm
 * @param {number} jd
 * @returns {boolean}
 */
export function isValidJalali(jy, jm, jd) {
    return isValidJalaaliDate(jy, jm, jd);
}

/**
 * @param {number} jy
 * @param {number} jm
 * @returns {number}
 */
export function jalaliMonthLength(jy, jm) {
    return jalaaliMonthLength(jy, jm);
}

/**
 * @param {number} jy
 * @returns {boolean}
 */
export function isJalaliLeap(jy) {
    return isLeapJalaaliYear(jy);
}
