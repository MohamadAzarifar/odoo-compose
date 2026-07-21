/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";

import { gregorianToJalali } from "@zvy_persian_calendar/js/jalali_core";
import {
    addJalaliMonths,
    adjustJalaliFocus,
    buildJalaliDaysItems,
    getJalaliInputPlaceholder,
    getJalaliMonthTitle,
    stepJalaliFocusDate,
} from "@zvy_persian_calendar/js/jalali_picker_utils";

const { DateTime } = luxon;

describe.current.tags("headless");

describe("jalali_picker_utils", () => {
    test("addJalaliMonths rolls over year boundary", () => {
        expect(addJalaliMonths(1403, 12, 1)).toEqual({ jy: 1404, jm: 1 });
        expect(addJalaliMonths(1404, 1, -1)).toEqual({ jy: 1403, jm: 12 });
    });

    test("jalaliMonthStart maps Farvardin 1403 to 2024-03-20", () => {
        expect(jalaliMonthStart(1403, 1).toISODate()).toBe("2024-03-20");
    });

    test("getJalaliMonthTitle for Nowruz month (Latin UI)", () => {
        const date = DateTime.fromISO("2024-03-20");
        // Title uses current UI language; Latin transliteration when not fa_*
        const title = getJalaliMonthTitle(date);
        expect(title === "Farvardin 1403" || title === "فروردین 1403").toBe(true);
    });

    test("buildJalaliDaysItems includes 1 Farvardin in the month grid", () => {
        const focusDate = DateTime.fromISO("2024-03-20");
        const items = buildJalaliDaysItems(focusDate, {
            minDate: DateTime.fromObject({ year: 1000 }),
            maxDate: DateTime.fromObject({ year: 9999 }).endOf("year"),
            showWeekNumbers: false,
        });
        const allDays = items[0].weeks.flatMap((week) => week.days);
        const firstOfMonth = allDays.find((day) => !day.isOutOfRange && day.label === "1");
        expect(firstOfMonth).toBeTruthy();
        expect(gregorianToJalali(firstOfMonth.range[0])).toEqual({ jy: 1403, jm: 1, jd: 1 });
    });

    test("stepJalaliFocusDate navigates to next Jalali month", () => {
        const focusDate = DateTime.fromISO("2024-03-20");
        const next = stepJalaliFocusDate(focusDate, "days", "next");
        const focusJalali = gregorianToJalali(focusDate);
        const nextJalali = gregorianToJalali(next);
        expect(nextJalali.jm).toBe(focusJalali.jm + 1);
        expect(nextJalali.jd).toBe(1);
    });

    test("adjustJalaliFocus snaps to Jalali month start", () => {
        const date = DateTime.fromISO("2024-04-15");
        const adjusted = adjustJalaliFocus(date);
        const adjustedJalali = gregorianToJalali(adjusted);
        const dateJalali = gregorianToJalali(date);
        expect(adjustedJalali.jm).toBe(dateJalali.jm);
        expect(adjustedJalali.jd).toBe(1);
    });

    test("getJalaliInputPlaceholder returns sample Jalali date", () => {
        expect(getJalaliInputPlaceholder("date")).toBe("1403/07/21");
        expect(getJalaliInputPlaceholder("datetime")).toBe("1403/07/21 14:30");
    });
});
