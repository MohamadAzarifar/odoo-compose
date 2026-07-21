/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";

import { gregorianToJalali } from "@zvy_persian_calendar/js/jalali_core";
import {
    computeJalaliCalendarRange,
    formatJalaliMonthYear,
    formatJalaliWeekHeader,
    isOutsideJalaliMonth,
    stepJalaliCalendarDate,
    toFullCalendarVisibleRange,
} from "@zvy_persian_calendar/js/jalali_calendar_utils";

const { DateTime } = luxon;

describe.current.tags("headless");

describe("jalali_calendar_utils", () => {
    test("computeJalaliCalendarRange month is Farvardin 1403 (with overflow weeks)", () => {
        // 2024-03-25 = 6 Farvardin 1403; weekStart Monday (firstDayOfWeek=1)
        const date = DateTime.fromISO("2024-03-25");
        const { start, end } = computeJalaliCalendarRange({
            scale: "month",
            date,
            firstDayOfWeek: 1,
            monthOverflow: true,
        });
        // Farvardin 1 1403 = 2024-03-20 (Wednesday) → week starts Monday 2024-03-18
        expect(start.toISODate()).toBe("2024-03-18");
        // 6 weeks from start minus 1 day
        expect(end.toISODate()).toBe("2024-04-28");
    });

    test("computeJalaliCalendarRange month without overflow is exact Jalali month", () => {
        const date = DateTime.fromISO("2024-03-25");
        const { start, end } = computeJalaliCalendarRange({
            scale: "month",
            date,
            firstDayOfWeek: 1,
            monthOverflow: false,
        });
        expect(start.toISODate()).toBe("2024-03-20");
        expect(end.toISODate()).toBe("2024-04-19");
        expect(gregorianToJalali(start)).toEqual({ jy: 1403, jm: 1, jd: 1 });
        expect(gregorianToJalali(end)).toEqual({ jy: 1403, jm: 1, jd: 31 });
    });

    test("computeJalaliCalendarRange year spans Farvardin–Esfand", () => {
        const date = DateTime.fromISO("2024-10-12"); // Mehr 1403
        const { start, end } = computeJalaliCalendarRange({
            scale: "year",
            date,
            firstDayOfWeek: 1,
            monthOverflow: true,
        });
        expect(gregorianToJalali(start)).toEqual({ jy: 1403, jm: 1, jd: 1 });
        expect(gregorianToJalali(end).jy).toBe(1403);
        expect(gregorianToJalali(end).jm).toBe(12);
    });

    test("stepJalaliCalendarDate next month crosses year (Esfand → Farvardin)", () => {
        // 1403/12/15 ≈ 2025-03-05
        const date = DateTime.fromISO("2025-03-05");
        const next = stepJalaliCalendarDate(date, "month", "next");
        expect(gregorianToJalali(next)).toEqual({ jy: 1404, jm: 1, jd: 15 });
    });

    test("formatJalaliMonthYear for Mehr 1403", () => {
        const date = DateTime.fromISO("2024-10-12");
        const title = formatJalaliMonthYear(date);
        expect(title === "Mehr 1403" || title === "مهر ۱۴۰۳" || title === "مهر 1403").toBe(true);
    });

    test("formatJalaliWeekHeader spans months", () => {
        const start = DateTime.fromISO("2024-03-18");
        const end = DateTime.fromISO("2024-03-24");
        const header = formatJalaliWeekHeader(start, end);
        // Week covers Esfand 1402 and Farvardin 1403
        expect(header.includes("1402") || header.includes("1403")).toBe(true);
    });

    test("isOutsideJalaliMonth detects overflow cells", () => {
        const focus = DateTime.fromISO("2024-03-25"); // Farvardin
        const outside = DateTime.fromISO("2024-03-19"); // Esfand 1402
        const inside = DateTime.fromISO("2024-03-20");
        expect(isOutsideJalaliMonth(outside, focus)).toBe(true);
        expect(isOutsideJalaliMonth(inside, focus)).toBe(false);
    });

    test("toFullCalendarVisibleRange end is exclusive", () => {
        const start = DateTime.fromISO("2024-03-20");
        const end = DateTime.fromISO("2024-04-19");
        expect(toFullCalendarVisibleRange(start, end)).toEqual({
            start: "2024-03-20",
            end: "2024-04-20",
        });
    });
});
