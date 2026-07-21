/** @odoo-module **/

import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { dateField, dateTimeField } from "@web/views/fields/datetime/datetime_field";
import { patch } from "@web/core/utils/patch";
import { getJalaliInputPlaceholder } from "@zvy_persian_calendar/js/jalali_picker_utils";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

function withJalaliPlaceholder(props, type, placeholder) {
    if (isJalaliActive() && !placeholder) {
        props.placeholder = getJalaliInputPlaceholder(type);
    }
    return props;
}

patch(dateField, {
    extractProps(params, dynamicInfo) {
        const props = super.extractProps(params, dynamicInfo);
        return withJalaliPlaceholder(props, "date", params.placeholder);
    },
});

patch(dateTimeField, {
    extractProps(params, dynamicInfo) {
        const props = super.extractProps(params, dynamicInfo);
        return withJalaliPlaceholder(props, "datetime", params.placeholder);
    },
});

patch(DateTimeInput.prototype, {
    get jalaliPlaceholder() {
        if (this.props.placeholder) {
            return this.props.placeholder;
        }
        if (isJalaliActive()) {
            return getJalaliInputPlaceholder(this.props.type || "datetime");
        }
        return "";
    },
});
