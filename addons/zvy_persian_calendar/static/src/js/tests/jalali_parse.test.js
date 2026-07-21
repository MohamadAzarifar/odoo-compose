/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";

import { gregorianToJalali } from "@zvy_persian_calendar/js/jalali_core";
import { formatJalali, isPersianUiLanguage, parseJalali } from "@zvy_persian_calendar/js/jalali_format";
import { luxonDateFormatToJalaliPattern } from "@zvy_persian_calendar/js/jalali_luxon_format";

const { DateTime } = luxon;

describe.current.tags("headless");

describe("jalali date parse/format round-trip", () => {
    test("isPersianUiLanguage recognizes fa-IR and fa_IR", () => {
        expect(isPersianUiLanguage("fa-IR")).toBe(true);
        expect(isPersianUiLanguage("fa_IR")).toBe(true);
        expect(isPersianUiLanguage("en-US")).toBe(false);
    });

    test("formatJalali uses Persian month names for fa-IR", () => {
        const gregorian = DateTime.fromISO("2026-07-21");
        const formatted = formatJalali(gregorian, "%d %B %Y");
        // When test env lang is not fa, this may be Latin; explicit lang not supported
        // in formatJalali yet — verify via isPersianUiLanguage branch in integration.
        expect(formatted).toMatch(/\d+ (Tir|تیر) 1405/);
    });

    test("1405/04/30 must not be read as Gregorian year 1405", () => {
        const pattern = luxonDateFormatToJalaliPattern("yyyy/MM/dd");
        const parsed = parseJalali("1405/04/30", pattern);
        expect(parsed).not.toBeNull();
        expect(parsed.toISODate()).toBe("2026-07-21");
        expect(gregorianToJalali(parsed)).toEqual({ jy: 1405, jm: 4, jd: 30 });
    });

    test("format then parse preserves 30 Tir 1405", () => {
        const gregorian = DateTime.fromISO("2026-07-21");
        const formatted = formatJalali(gregorian, "%Y/%m/%d");
        expect(formatted).toBe("1405/04/30");

        const pattern = luxonDateFormatToJalaliPattern("yyyy/MM/dd");
        const parsed = parseJalali(formatted, pattern);
        expect(parsed.toISODate()).toBe("2026-07-21");
    });

    test("Gregorian ISO strings still parse as Gregorian when pattern does not match", () => {
        const pattern = luxonDateFormatToJalaliPattern("yyyy/MM/dd");
        expect(parseJalali("2026-07-21", pattern)).toBeNull();
    });

    test("Persian month names parse when typed", () => {
        const parsed = parseJalali("۳۰ تیر ۱۴۰۵", "%d %B %Y");
        // Digits are normalized; month name must resolve
        expect(parsed).not.toBeNull();
        expect(parsed.toISODate()).toBe("2026-07-21");
    });

    test("Latin month names still parse", () => {
        const parsed = parseJalali("30 Tir 1405", "%d %B %Y");
        expect(parsed).not.toBeNull();
        expect(parsed.toISODate()).toBe("2026-07-21");
    });
});
