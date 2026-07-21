/** @odoo-module **/

import { DateTimePicker } from "@web/core/datetime/datetime_picker";
import { today } from "@web/core/l10n/dates";
import { patch } from "@web/core/utils/patch";
import {
    adjustJalaliFocus,
    buildJalaliPrecisionItems,
    getJalaliPrecisionTitle,
    stepJalaliFocusDate,
} from "@zvy_persian_calendar/js/jalali_picker_utils";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

patch(DateTimePicker.prototype, {
    get isJalaliCalendar() {
        return isJalaliActive();
    },

    adjustFocus(values, focusedDateIndex) {
        if (!isJalaliActive() || this.state.precision !== "days") {
            return super.adjustFocus(...arguments);
        }
        if (!this.shouldAdjustFocusDate && this.state.focusDate) {
            return;
        }
        const dateToFocus =
            values[focusedDateIndex] || values[focusedDateIndex === 1 ? 0 : 1] || today();
        this.shouldAdjustFocusDate = false;
        this.state.focusDate = this.clamp(adjustJalaliFocus(dateToFocus));
    },

    onWillRender() {
        if (!isJalaliActive()) {
            return super.onWillRender(...arguments);
        }
        const { dayCellClass, focusedDateIndex, isDateValid, range, showWeekNumbers } = this.props;
        const { focusDate, hoveredDate, precision } = this.state;
        const getterParams = {
            maxDate: this.maxDate,
            minDate: this.minDate,
            showWeekNumbers: showWeekNumbers ?? !range,
            isDateValid,
            dayCellClass,
        };

        this.title = getJalaliPrecisionTitle(focusDate, precision);
        this.items = buildJalaliPrecisionItems(focusDate, precision, getterParams);

        this.selectedRange = [...this.values];
        if (range && focusedDateIndex > 0 && (!this.values[1] || hoveredDate > this.values[0])) {
            this.selectedRange[1] = hoveredDate;
        }
    },

    next(ev) {
        if (!isJalaliActive()) {
            return super.next(...arguments);
        }
        ev.preventDefault();
        this.state.focusDate = this.clamp(
            stepJalaliFocusDate(this.state.focusDate, this.state.precision, "next")
        );
    },

    previous(ev) {
        if (!isJalaliActive()) {
            return super.previous(...arguments);
        }
        ev.preventDefault();
        this.state.focusDate = this.clamp(
            stepJalaliFocusDate(this.state.focusDate, this.state.precision, "previous")
        );
    },
});
