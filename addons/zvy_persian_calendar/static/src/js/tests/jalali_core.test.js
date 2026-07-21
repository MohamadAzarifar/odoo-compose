/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";

import {
    gregorianToJalali,
    isJalaliLeap,
    isValidJalali,
    jalaliMonthLength,
    jalaliToGregorian,
} from "@zvy_persian_calendar/js/jalali_core";

const { DateTime } = luxon;

describe.current.tags("headless");

describe("jalali_core", () => {
    test("Nowruz 1403 maps to 2024-03-20", () => {
        const jalali = gregorianToJalali(DateTime.fromISO("2024-03-20"));
        expect(jalali).toEqual({ jy: 1403, jm: 1, jd: 1 });
    });

    test("Nowruz 1404 maps to 2025-03-21", () => {
        const jalali = gregorianToJalali(DateTime.fromISO("2025-03-21"));
        expect(jalali).toEqual({ jy: 1404, jm: 1, jd: 1 });
    });

    test("leap year 1403 has 30 days in Esfand", () => {
        expect(isJalaliLeap(1403)).toBe(true);
        expect(jalaliMonthLength(1403, 12)).toBe(30);
        expect(isValidJalali(1403, 12, 30)).toBe(true);
    });

    test("non-leap year 1402 has 29 days in Esfand", () => {
        expect(isJalaliLeap(1402)).toBe(false);
        expect(jalaliMonthLength(1402, 12)).toBe(29);
        expect(isValidJalali(1402, 12, 30)).toBe(false);
    });

    test("round-trip Gregorian → Jalali → Gregorian", () => {
        const original = DateTime.fromISO("2024-11-11");
        const jalali = gregorianToJalali(original);
        const back = jalaliToGregorian(jalali.jy, jalali.jm, jalali.jd);
        expect(back.toISODate()).toBe(original.toISODate());
    });
});
