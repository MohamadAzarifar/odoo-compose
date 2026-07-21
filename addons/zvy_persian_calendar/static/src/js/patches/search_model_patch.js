/** @odoo-module **/

import { SearchModel } from "@web/search/search_model";
import { patch } from "@web/core/utils/patch";
import {
    constructJalaliDateDomain,
    getJalaliPeriodOptions,
} from "@zvy_persian_calendar/js/jalali_search_utils";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";
import { yearSelected } from "@web/search/utils/dates";

/**
 * SearchModel keeps named imports of constructDateDomain / getPeriodOptions.
 * Patch the call sites so Jalali domains and period labels apply even when the
 * module-level patch is not visible to those bindings.
 */
patch(SearchModel.prototype, {
    _getDateFilterDomain(dateFilter, generatorIds, key = "domain") {
        if (!isJalaliActive()) {
            return super._getDateFilterDomain(...arguments);
        }
        const dateFilterRange = constructJalaliDateDomain(
            this.referenceMoment,
            dateFilter,
            generatorIds
        );
        return dateFilterRange[key];
    },

    _enrichItem(searchItem) {
        if (!isJalaliActive() || searchItem.type !== "dateFilter") {
            return super._enrichItem(...arguments);
        }
        // Mirror stock _enrichItem but with Jalali period option labels.
        if (searchItem.type === "field" && searchItem.fieldType === "properties") {
            return { ...searchItem };
        }
        const queryElements = this.query.filter(
            (queryElem) => queryElem.searchItemId === searchItem.id
        );
        const isActive = Boolean(queryElements.length);
        const enrichSearchItem = Object.assign({ isActive }, searchItem);
        enrichSearchItem.options = getJalaliPeriodOptions(
            this.referenceMoment,
            searchItem.optionsParams
        ).map((o) => {
            const { description, id, groupNumber } = o;
            const optionActive = queryElements.some(
                (queryElem) => queryElem.generatorId === id
            );
            return { description, id, groupNumber, isActive: optionActive };
        });
        return enrichSearchItem;
    },

    toggleDateFilter(searchItemId, generatorId) {
        if (!isJalaliActive()) {
            return super.toggleDateFilter(...arguments);
        }
        const searchItem = this.searchItems[searchItemId];
        if (searchItem.type !== "dateFilter") {
            return;
        }
        const generatorIds = generatorId ? [generatorId] : searchItem.defaultGeneratorIds;
        for (const genId of generatorIds) {
            const index = this.query.findIndex(
                (queryElem) =>
                    queryElem.searchItemId === searchItemId &&
                    "generatorId" in queryElem &&
                    queryElem.generatorId === genId
            );
            if (index >= 0) {
                this.query.splice(index, 1);
                if (!yearSelected(this._getSelectedGeneratorIds(searchItemId))) {
                    this.query = this.query.filter(
                        (queryElem) => queryElem.searchItemId !== searchItemId
                    );
                }
            } else {
                if (genId.startsWith("custom")) {
                    this.query = this.query.filter(
                        (queryElem) => searchItemId !== queryElem.searchItemId
                    );
                    this.query.push({ searchItemId, generatorId: genId });
                    continue;
                }
                this.query = this.query.filter(
                    (queryElem) =>
                        queryElem.searchItemId !== searchItemId ||
                        !queryElem.generatorId.startsWith("custom")
                );
                this.query.push({ searchItemId, generatorId: genId });
                if (!yearSelected(this._getSelectedGeneratorIds(searchItemId))) {
                    const { defaultYearId } = getJalaliPeriodOptions(
                        this.referenceMoment,
                        searchItem.optionsParams
                    ).find((o) => o.id === genId);
                    this.query.push({ searchItemId, generatorId: defaultYearId });
                }
            }
        }
        this._notify();
    },
});
