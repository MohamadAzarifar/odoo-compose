/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { today } from "@web/core/l10n/dates";
import * as domainFromTreeModule from "@web/core/tree_editor/domain_from_tree";
import * as expressionFromTreeModule from "@web/core/tree_editor/expression_from_tree";
import * as virtualOperators from "@web/core/tree_editor/virtual_operators";
import { getJalaliSmartDateBounds } from "@zvy_persian_calendar/js/jalali_search_utils";
import { isJalaliActive } from "@zvy_persian_calendar/js/jalali_service";

/**
 * When Jalali is active, month/year “in range” presets become absolute Gregorian
 * bounds derived from the current Jalali month/year. Day-based presets (today,
 * last 7/30 days) stay stock-relative.
 *
 * Custom range uses DateTimeInput → Phase 2B Jalali picker (no change here).
 *
 * Limitation: absolute bounds are fixed when the domain is built; prefer
 * Filters → Date period toggles for recurring “this month / this year”.
 */

const JALALI_RANGE_TYPES = new Set([
    "month to date",
    "last month",
    "year to date",
    "last 12 months",
]);

patch(virtualOperators, {
    eliminateVirtualOperators(tree, options = {}) {
        if (!isJalaliActive()) {
            return super.eliminateVirtualOperators(...arguments);
        }
        return super.eliminateVirtualOperators(rewriteJalaliInRangeConditions(tree), options);
    },
});

patch(domainFromTreeModule, {
    domainFromTree(tree) {
        if (!isJalaliActive()) {
            return super.domainFromTree(...arguments);
        }
        return super.domainFromTree(rewriteJalaliInRangeConditions(tree));
    },
});

patch(expressionFromTreeModule, {
    expressionFromTree(tree, options) {
        if (!isJalaliActive()) {
            return super.expressionFromTree(...arguments);
        }
        return super.expressionFromTree(rewriteJalaliInRangeConditions(tree), options);
    },
});

/**
 * @param {object} tree
 * @returns {object}
 */
function rewriteJalaliInRangeConditions(tree) {
    if (!tree || typeof tree !== "object") {
        return tree;
    }
    if (tree.type === "connector") {
        return {
            ...tree,
            children: tree.children.map(rewriteJalaliInRangeConditions),
        };
    }
    if (tree.type === "condition" && tree.operator === "any" && tree.value) {
        return {
            ...tree,
            value: rewriteJalaliInRangeConditions(tree.value),
        };
    }
    if (tree.type !== "condition" || tree.operator !== "in range") {
        return tree;
    }
    const [fieldType, valueType] = tree.value || [];
    if (valueType === "custom range" || !JALALI_RANGE_TYPES.has(valueType)) {
        return tree;
    }
    const bounds = getJalaliSmartDateBounds(today(), fieldType, valueType);
    if (!bounds) {
        return tree;
    }
    const [left, rightExclusive] = bounds;
    return {
        type: "connector",
        value: "&",
        negate: Boolean(tree.negate),
        children: [
            {
                type: "condition",
                path: tree.path,
                operator: ">=",
                value: left,
                negate: false,
                isProperty: tree.isProperty,
            },
            {
                type: "condition",
                path: tree.path,
                operator: "<",
                value: rightExclusive,
                negate: false,
                isProperty: tree.isProperty,
            },
        ],
    };
}
