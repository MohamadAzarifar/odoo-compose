/** @odoo-module **/

import * as searchDates from "@web/search/utils/dates";
import { patch } from "@web/core/utils/patch";
import {
    constructJalaliDateDomain,
    getJalaliPeriodOptions,
} from "@zvy_persian_calendar/js/jalali_search_utils";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

patch(searchDates, {
    constructDateDomain(referenceMoment, searchItem, selectedOptionIds) {
        if (!isJalaliActive()) {
            return super.constructDateDomain(...arguments);
        }
        return constructJalaliDateDomain(referenceMoment, searchItem, selectedOptionIds);
    },

    getPeriodOptions(referenceMoment, optionsParams) {
        if (!isJalaliActive()) {
            return super.getPeriodOptions(...arguments);
        }
        return getJalaliPeriodOptions(referenceMoment, optionsParams);
    },
});
