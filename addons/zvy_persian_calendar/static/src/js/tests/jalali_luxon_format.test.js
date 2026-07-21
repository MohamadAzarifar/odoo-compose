/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";

import {
    luxonDateFormatToJalaliPattern,
    splitLuxonDateTimeFormat,
} from "@zvy_persian_calendar/js/jalali_luxon_format";
import { formatJalali } from "@zvy_persian_calendar/js/jalali_format";

const { DateTime } = luxon;

describe.current.tags("headless");

describe("jalali_luxon_format", () => {
    test("maps common Luxon date tokens to jalali patterns", () => {
        expect(luxonDateFormatToJalaliPattern("yyyy/MM/dd")).toBe("%Y/%m/%d");
        expect(luxonDateFormatToJalaliPattern("dd MMM yyyy")).toBe("%d %b %Y");
        expect(luxonDateFormatToJalaliPattern("d M yyyy")).toBe("%-d %-m %Y");
    });

    test("splits datetime format into date and time parts", () => {
        expect(splitLuxonDateTimeFormat("yyyy/MM/dd HH:mm:ss")).toEqual([
            "yyyy/MM/dd",
            "HH:mm:ss",
        ]);
        expect(splitLuxonDateTimeFormat("yyyy/MM/dd")).toEqual(["yyyy/MM/dd", ""]);
    });

    test("formats Nowruz 1403 with fa_IR-style pattern", () => {
        const date = DateTime.fromISO("2024-03-20");
        const pattern = luxonDateFormatToJalaliPattern("yyyy/MM/dd");
        expect(formatJalali(date, pattern)).toBe("1403/01/01");
    });
});
