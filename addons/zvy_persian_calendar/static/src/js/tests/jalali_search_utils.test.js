/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import { Domain } from "@web/core/domain";

import { gregorianToJalali } from "@zvy_persian_calendar/js/jalali_core";
import {
    constructJalaliDateDomain,
    getJalaliPeriodOptions,
    getJalaliQuarterLabel,
    getJalaliSmartDateBounds,
    jalaliMonthBounds,
    jalaliQuarterBounds,
    jalaliYearBounds,
} from "@zvy_persian_calendar/js/jalali_search_utils";

const { DateTime } = luxon;

describe.current.tags("headless");

const dateSearchItem = {
    fieldName: "date_field",
    fieldType: "date",
    domain: "[]",
    optionsParams: {
        customOptions: [],
        endMonth: 0,
        endYear: 0,
        startMonth: -2,
        startYear: -2,
    },
    type: "dateFilter",
};

describe("jalali_search_utils", () => {
    test("Farvardin 1 and Esfand end have no off-by-one (1403 leap)", () => {
        // 1403 is leap → Esfand has 30 days; Farvardin 1 1403 = 2024-03-20
        const year = jalaliYearBounds(1403);
        expect(year.left.toISODate()).toBe("2024-03-20");
        expect(gregorianToJalali(year.left)).toEqual({ jy: 1403, jm: 1, jd: 1 });
        expect(gregorianToJalali(year.right)).toEqual({ jy: 1403, jm: 12, jd: 30 });
        expect(year.right.toISODate()).toBe("2025-03-20");

        const farvardin = jalaliMonthBounds(1403, 1);
        expect(farvardin.left.toISODate()).toBe("2024-03-20");
        expect(farvardin.right.toISODate()).toBe("2024-04-19");

        const esfand = jalaliMonthBounds(1403, 12);
        expect(esfand.left.toISODate()).toBe("2025-02-19");
        expect(esfand.right.toISODate()).toBe("2025-03-20");
    });

    test("Esfand non-leap year ends on day 29", () => {
        // 1402 is common → Esfand 29 = 2024-03-19
        const esfand = jalaliMonthBounds(1402, 12);
        expect(gregorianToJalali(esfand.right)).toEqual({ jy: 1402, jm: 12, jd: 29 });
        expect(esfand.right.toISODate()).toBe("2024-03-19");
    });

    test("this month (Mehr 1403) domain is Gregorian Mehr bounds", () => {
        // 2024-10-12 = 21 Mehr 1403; Mehr 1403 = 2024-09-22 .. 2024-10-21
        const referenceMoment = DateTime.fromISO("2024-10-12T12:00:00");
        const { domain, description } = constructJalaliDateDomain(referenceMoment, dateSearchItem, [
            "month",
            "year",
        ]);
        expect(domain).toEqual(
            new Domain(
                `["&", ("date_field", ">=", "2024-09-22"), ("date_field", "<=", "2024-10-21")]`
            )
        );
        expect(description.includes("1403")).toBe(true);
        expect(description.toLowerCase().includes("mehr") || description.includes("مهر")).toBe(
            true
        );
    });

    test("this year (1403) domain is Farvardin–Esfand Gregorian range", () => {
        const referenceMoment = DateTime.fromISO("2024-10-12T12:00:00");
        const { domain, description } = constructJalaliDateDomain(referenceMoment, dateSearchItem, [
            "year",
        ]);
        expect(domain).toEqual(
            new Domain(
                `["&", ("date_field", ">=", "2024-03-20"), ("date_field", "<=", "2025-03-20")]`
            )
        );
        expect(description).toBe("1403");
    });

    test("period options show Jalali month names and years", () => {
        const referenceMoment = DateTime.fromISO("2024-10-12T12:00:00");
        const options = getJalaliPeriodOptions(referenceMoment, dateSearchItem.optionsParams);
        const month = options.find((o) => o.id === "month");
        const year = options.find((o) => o.id === "year");
        expect(month.description === "Mehr" || month.description === "مهر").toBe(true);
        expect(year.description).toBe("1403");
        expect(month.defaultYearId).toBe("year");
    });

    test("Q1 Jalali is Farvardin–Khordad", () => {
        const q1 = jalaliQuarterBounds(1403, 1);
        expect(q1.left.toISODate()).toBe("2024-03-20");
        expect(gregorianToJalali(q1.right)).toEqual({ jy: 1403, jm: 3, jd: 31 });
    });

    test("quarter labels are consistent (not mixed Q1/س۱ from stock fa.po)", () => {
        expect(getJalaliQuarterLabel(1, "en_US")).toBe("Q1");
        expect(getJalaliQuarterLabel(2, "en_US")).toBe("Q2");
        expect(getJalaliQuarterLabel(3, "en_US")).toBe("Q3");
        expect(getJalaliQuarterLabel(4, "en_US")).toBe("Q4");
        expect(getJalaliQuarterLabel(1, "fa_IR")).toBe("س۱");
        expect(getJalaliQuarterLabel(2, "fa_IR")).toBe("س۲");
        expect(getJalaliQuarterLabel(3, "fa_IR")).toBe("س۳");
        expect(getJalaliQuarterLabel(4, "fa_IR")).toBe("س۴");
    });

    test("year to date smart bounds use Jalali year start", () => {
        const referenceMoment = DateTime.fromISO("2024-10-12T12:00:00");
        const [left, right] = getJalaliSmartDateBounds(referenceMoment, "date", "year to date");
        expect(left).toBe("2024-03-20");
        expect(right).toBe("2024-10-13"); // exclusive end (tomorrow)
    });

    test("month to date smart bounds use Jalali month start", () => {
        const referenceMoment = DateTime.fromISO("2024-10-12T12:00:00");
        const [left, right] = getJalaliSmartDateBounds(referenceMoment, "date", "month to date");
        expect(left).toBe("2024-09-22");
        expect(right).toBe("2024-10-13");
    });
});
