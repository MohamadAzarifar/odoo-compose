/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { formatMonetary } from "@web/views/fields/formatters";

const PROPERTY_STATE_ORDER = ["draft", "available", "reserved", "booked", "sold", "transferred", "blocked"];
const INSTALLMENT_STATE_ORDER = ["pending", "invoiced", "partial", "paid", "overdue", "cancelled"];
const BOOKING_STATE_ORDER = ["draft", "confirmed", "in_payment", "completed", "cancelled"];
const TRANSFER_STATE_ORDER = ["draft", "in_review", "approved", "completed", "cancelled"];

// Catalog of selectable KPI tiles for the top strip. The backend owns the
// numbers; here we hold the presentation (icon / colour) and drill-down target.
const KPI_DEFS = {
    projects: { icon: "fa-building", cls: "o_sa_kpi_indigo", click: "properties" },
    properties: { icon: "fa-home", cls: "o_sa_kpi_blue", click: "properties" },
    available: { icon: "fa-check-circle", cls: "o_sa_kpi_green", click: "properties:available" },
    reserved: { icon: "fa-bookmark", cls: "o_sa_kpi_amber", click: "properties:reserved" },
    booked: { icon: "fa-calendar-check-o", cls: "o_sa_kpi_blue", click: "properties:booked" },
    sold: { icon: "fa-trophy", cls: "o_sa_kpi_violet", click: "properties:sold", pct: "sell_through" },
    active_bookings: { icon: "fa-handshake-o", cls: "o_sa_kpi_teal", click: "bookings:in_payment" },
    completed_bookings: { icon: "fa-check", cls: "o_sa_kpi_green", click: "bookings:completed" },
    transfers_pending: { icon: "fa-exchange", cls: "o_sa_kpi_amber", click: "transfers" },
    transfers_completed: { icon: "fa-exchange", cls: "o_sa_kpi_green", click: "transfers:completed" },
    overdue_count: { icon: "fa-exclamation-triangle", cls: "o_sa_kpi_red", click: "overdue" },
};

const CUSTOM_PALETTE = ["#6366F1", "#10B981", "#F59E0B", "#EF4444", "#3B82F6", "#8B5CF6", "#14B8A6", "#F472B6"];

function orderBy(rows, order) {
    const idx = (k) => {
        const i = order.indexOf(k);
        return i === -1 ? order.length : i;
    };
    return [...rows].sort((a, b) => idx(a.key) - idx(b.key));
}

export class SaPropertyDashboard extends Component {
    static template = "sa_property_management.Dashboard";
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: [Number, String, Boolean], optional: true },
        className: { type: String, optional: true },
        globalState: { type: Object, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            data: null,
            error: null,
            meta: null,
            layout: null,
            isManager: false,
            editMode: false,
            saving: false,
            draft: { title: "", model: "", measure: "", group_by: "", chart: "bar" },
        });
        this.charts = {};
        this.dragIndex = null;
        this._pendingRender = false;
        this.rootRef = useRef("root");
        this.refs = {
            propertyState: useRef("propertyStateChart"),
            propertyType: useRef("propertyTypeChart"),
            projectInventory: useRef("projectInventoryChart"),
            bookingState: useRef("bookingStateChart"),
            bookingTrend: useRef("bookingTrendChart"),
            installmentState: useRef("installmentStateChart"),
            aging: useRef("agingChart"),
            collectionTrend: useRef("collectionTrendChart"),
            receivableVsReceived: useRef("receivableVsReceivedChart"),
            transferState: useRef("transferStateChart"),
            transferTax: useRef("transferTaxChart"),
        };

        onWillStart(async () => {
            try {
                await loadJS("/web/static/lib/Chart/Chart.js");
                const bundle = await this.orm.call(
                    "sa.property.dashboard",
                    "get_dashboard_bundle",
                    []
                );
                this.state.data = bundle.data;
                this.state.meta = bundle.meta;
                this.state.layout = bundle.layout;
                this.state.isManager = bundle.is_manager;
            } catch (err) {
                this.state.error = err.message || String(err);
            } finally {
                this.state.loading = false;
            }
        });

        onMounted(() => {
            if (this.state.data && !this.state.loading) {
                this._renderAllCharts();
            }
        });

        // The dashboard body (and every <canvas>) is conditionally rendered.
        // Whenever a state change re-paints it, redraw the charts once the DOM
        // is in place. This is reliable for dynamically added custom widgets,
        // section reordering and filter reloads — unlike a raced setTimeout.
        onPatched(() => {
            if (this._pendingRender && !this.state.loading && this.state.data) {
                this._pendingRender = false;
                this._renderAllCharts();
            }
        });

        onWillUnmount(() => {
            this._destroyCharts();
        });
    }

    // ------------------------------------------------------------------
    // Formatting helpers
    // ------------------------------------------------------------------
    fmtMoney(value) {
        const cur = this.state.data?.currency;
        if (!cur) return value;
        try {
            return formatMonetary(value, { currencyId: false }) + " " + (cur.symbol || cur.name);
        } catch (_e) {
            return `${(cur.symbol || cur.name) || ""} ${Number(value || 0).toLocaleString()}`;
        }
    }

    fmtInt(v) {
        return Number(v || 0).toLocaleString();
    }

    fmtCompact(v) {
        v = Number(v || 0);
        const sign = v < 0 ? "-" : "";
        v = Math.abs(v);
        if (v >= 1e9) return sign + (v / 1e9).toFixed(2) + "B";
        if (v >= 1e7) return sign + (v / 1e7).toFixed(2) + "Cr"; // Pakistani crore
        if (v >= 1e5) return sign + (v / 1e5).toFixed(2) + "L"; // Pakistani lakh
        if (v >= 1e3) return sign + (v / 1e3).toFixed(1) + "K";
        return sign + v.toFixed(0);
    }

    fmtCompactMoney(v) {
        const cur = this.state.data?.currency;
        return `${(cur?.symbol || cur?.name) || ""} ${this.fmtCompact(v)}`;
    }

    // ------------------------------------------------------------------
    // Drill-down navigation
    // ------------------------------------------------------------------
    _openList(model, name, domain = [], viewMode = "list,form") {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            views: viewMode.split(",").map((v) => [false, v]),
            domain,
            target: "current",
        });
    }

    openProperties(state) {
        const domain = state ? [["state", "=", state]] : [];
        const label = state ? `Properties - ${state}` : "Properties";
        return this._openList("sa.property", label, domain, "kanban,list,form");
    }

    openProjectProperties(projectId) {
        return this._openList(
            "sa.property",
            "Properties",
            [["project_id", "=", projectId]],
            "kanban,list,form"
        );
    }

    openBookings(state) {
        const domain = state ? [["state", "=", state]] : [];
        const label = state ? `Bookings - ${state}` : "Bookings";
        return this._openList("sa.property.booking", label, domain);
    }

    openInstallments(state) {
        const domain = state ? [["state", "=", state]] : [];
        const label = state ? `Installments - ${state}` : "Installments";
        return this._openList("sa.property.installment", label, domain);
    }

    openOverdue() {
        return this._openList(
            "sa.property.installment",
            "Overdue Installments",
            [["state", "=", "overdue"]]
        );
    }

    openUpcoming() {
        const data = this.state.data;
        return this._openList(
            "sa.property.installment",
            "Upcoming Installments",
            [
                ["state", "in", ["pending", "invoiced", "partial"]],
                ["due_date", ">=", data.today],
            ]
        );
    }

    openTransfers(state) {
        const domain = state ? [["state", "=", state]] : [];
        const label = state ? `Transfers - ${state}` : "Transfers";
        return this._openList("sa.property.transfer", label, domain);
    }

    openOneInstallment(id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sa.property.installment",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openOneBooking(id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sa.property.booking",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openOneTransfer(id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sa.property.transfer",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    _destroyCharts() {
        Object.values(this.charts).forEach((c) => c && c.destroy());
        this.charts = {};
    }

    async reloadData() {
        this.state.loading = true;
        this._destroyCharts();
        try {
            this.state.data = await this.orm.call(
                "sa.property.dashboard",
                "get_dashboard_data",
                [this._raw(this.state.layout.filters), this._raw(this.state.layout.custom_widgets)]
            );
        } finally {
            this.state.loading = false;
            // Defer to onPatched so the freshly re-rendered canvases exist.
            this._pendingRender = true;
        }
    }

    async refresh() {
        await this.reloadData();
    }

    _scheduleRerender() {
        // Flag a redraw; the state mutation that called us triggers onPatched.
        this._pendingRender = true;
    }

    _raw(value) {
        return JSON.parse(JSON.stringify(value));
    }

    // ------------------------------------------------------------------
    // Customization — KPI tiles
    // ------------------------------------------------------------------
    get visibleKpis() {
        const data = this.state.data;
        const catalog = this.state.meta ? this.state.meta.kpi_catalog : [];
        const labels = {};
        catalog.forEach((k) => (labels[k.key] = k.label));
        return (this.state.layout.kpis || [])
            .filter((k) => KPI_DEFS[k])
            .map((k) => {
                const def = KPI_DEFS[k];
                return {
                    key: k,
                    label: labels[k] || k,
                    icon: def.icon,
                    cls: def.cls,
                    value: this.fmtInt(data.kpi[k]),
                    pct: def.pct ? data.kpi[def.pct] : null,
                };
            });
    }

    onKpiClick(key) {
        const def = KPI_DEFS[key];
        if (!def || !def.click) return;
        const [action, arg] = def.click.split(":");
        if (action === "properties") return this.openProperties(arg);
        if (action === "bookings") return this.openBookings(arg);
        if (action === "transfers") return this.openTransfers(arg);
        if (action === "overdue") return this.openOverdue();
    }

    isKpiOn(key) {
        return (this.state.layout.kpis || []).includes(key);
    }

    toggleKpi(key) {
        const arr = this.state.layout.kpis;
        const i = arr.indexOf(key);
        if (i === -1) {
            arr.push(key);
        } else {
            arr.splice(i, 1);
        }
    }

    // ------------------------------------------------------------------
    // Customization — sections (visibility + ordering)
    // ------------------------------------------------------------------
    get orderedSections() {
        const labels = {};
        (this.state.meta ? this.state.meta.section_catalog : []).forEach(
            (s) => (labels[s.id] = s.label)
        );
        return (this.state.layout.sections || []).map((s) => ({
            id: s.id,
            visible: s.visible,
            label: labels[s.id] || s.id,
        }));
    }

    isSectionVisible(id) {
        const s = (this.state.layout.sections || []).find((x) => x.id === id);
        return s ? s.visible : false;
    }

    toggleSection(id) {
        const s = this.state.layout.sections.find((x) => x.id === id);
        if (s) {
            s.visible = !s.visible;
            this._scheduleRerender();
        }
    }

    moveSection(from, to) {
        const arr = this.state.layout.sections;
        if (to < 0 || to >= arr.length || from === to) return;
        const [item] = arr.splice(from, 1);
        arr.splice(to, 0, item);
        this._scheduleRerender();
    }

    onSectionDragStart(index) {
        this.dragIndex = index;
    }

    onSectionDragOver(ev) {
        ev.preventDefault();
    }

    onSectionDrop(index) {
        if (this.dragIndex !== null && this.dragIndex !== index) {
            this.moveSection(this.dragIndex, index);
        }
        this.dragIndex = null;
    }

    // ------------------------------------------------------------------
    // Customization — filters
    // ------------------------------------------------------------------
    isProjectOn(id) {
        return (this.state.layout.filters.project_ids || []).includes(id);
    }

    toggleProject(id) {
        const arr = this.state.layout.filters.project_ids;
        const i = arr.indexOf(id);
        if (i === -1) {
            arr.push(id);
        } else {
            arr.splice(i, 1);
        }
    }

    setDateFrom(ev) {
        this.state.layout.filters.date_from = ev.target.value || false;
    }

    setDateTo(ev) {
        this.state.layout.filters.date_to = ev.target.value || false;
    }

    async applyFilters() {
        await this.reloadData();
    }

    async clearFilters() {
        this.state.layout.filters = {
            project_ids: [],
            date_from: false,
            date_to: false,
        };
        await this.reloadData();
    }

    get hasActiveFilters() {
        const f = this.state.layout ? this.state.layout.filters : null;
        if (!f) return false;
        return (
            (f.project_ids && f.project_ids.length) ||
            f.date_from ||
            f.date_to
        );
    }

    // ------------------------------------------------------------------
    // Customization — custom widgets
    // ------------------------------------------------------------------
    get draftModelSpec() {
        return (this.state.meta ? this.state.meta.widget_models : []).find(
            (m) => m.model === this.state.draft.model
        );
    }

    onDraftModelChange(ev) {
        this.state.draft.model = ev.target.value;
        const spec = this.draftModelSpec;
        this.state.draft.measure = spec && spec.measures.length ? spec.measures[0].value : "__count";
        this.state.draft.group_by = spec && spec.groupbys.length ? spec.groupbys[0].value : "";
    }

    addCustomWidget() {
        const d = this.state.draft;
        if (!d.model || !d.group_by) {
            this.notification.add("Pick a source and a group-by first.", { type: "warning" });
            return;
        }
        this.state.layout.custom_widgets.push({
            id: "w" + Date.now(),
            title: d.title || "",
            model: d.model,
            measure: d.measure || "__count",
            group_by: d.group_by,
            chart: d.chart || "bar",
        });
        this.state.draft = { title: "", model: "", measure: "", group_by: "", chart: "bar" };
        this.reloadData();
    }

    removeCustomWidget(id) {
        const arr = this.state.layout.custom_widgets;
        const i = arr.findIndex((w) => w.id === id);
        if (i !== -1) {
            arr.splice(i, 1);
            this.reloadData();
        }
    }

    // ------------------------------------------------------------------
    // Customization — edit mode + persistence
    // ------------------------------------------------------------------
    toggleEdit() {
        this.state.editMode = !this.state.editMode;
    }

    _layoutPayload() {
        return this._raw({
            kpis: this.state.layout.kpis,
            sections: this.state.layout.sections,
            filters: this.state.layout.filters,
            custom_widgets: this.state.layout.custom_widgets,
        });
    }

    async saveLayout() {
        this.state.saving = true;
        try {
            const layout = await this.orm.call(
                "sa.property.dashboard",
                "save_dashboard_layout",
                [this._layoutPayload()]
            );
            this.state.layout = layout;
            this.state.editMode = false;
            this.notification.add("Dashboard layout saved.", { type: "success" });
            this._scheduleRerender();
        } finally {
            this.state.saving = false;
        }
    }

    async saveAsDefault() {
        this.state.saving = true;
        try {
            await this.orm.call(
                "sa.property.dashboard",
                "save_dashboard_default",
                [this._layoutPayload()]
            );
            this.notification.add("Saved as the company default dashboard.", { type: "success" });
        } finally {
            this.state.saving = false;
        }
    }

    async resetLayout() {
        const layout = await this.orm.call(
            "sa.property.dashboard",
            "reset_dashboard_layout",
            []
        );
        this.state.layout = layout;
        this.state.editMode = false;
        await this.reloadData();
        this.notification.add("Dashboard reset to default.", { type: "info" });
    }

    // ------------------------------------------------------------------
    // Chart rendering
    // ------------------------------------------------------------------
    _renderAllCharts() {
        if (!window.Chart || !this.state.data) return;
        // Sensible global defaults
        const Chart = window.Chart;
        Chart.defaults.font.family =
            "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
        Chart.defaults.color = "#374151";

        this._propertyStateDonut();
        this._propertyTypeDonut();
        this._projectInventoryStacked();
        this._bookingStateDonut();
        this._bookingTrendLine();
        this._installmentStateDonut();
        this._agingBar();
        this._collectionTrendBar();
        this._receivableVsReceivedBar();
        this._transferStateDonut();
        this._transferTaxBar();
        this._renderCustomCharts();
    }

    _renderCustomCharts() {
        const root = this.rootRef.el;
        if (!root || !window.Chart) return;
        (this.state.data.custom_widgets || []).forEach((w) => {
            const canvas = root.querySelector(`canvas[data-widget="${w.id}"]`);
            if (!canvas) return;
            const key = "custom_" + w.id;
            if (this.charts[key]) this.charts[key].destroy();
            const isPie = w.chart === "pie" || w.chart === "doughnut";
            const colors = w.labels.map((_l, i) => CUSTOM_PALETTE[i % CUSTOM_PALETTE.length]);
            this.charts[key] = new window.Chart(canvas.getContext("2d"), {
                type: w.chart,
                data: {
                    labels: w.labels,
                    datasets: [{
                        label: w.measure_label,
                        data: w.values,
                        backgroundColor: isPie ? colors : CUSTOM_PALETTE[0],
                        borderColor: isPie ? "#fff" : CUSTOM_PALETTE[0],
                        borderWidth: isPie ? 2 : 0,
                        borderRadius: isPie ? 0 : 6,
                        fill: w.chart === "line" ? false : true,
                        tension: 0.35,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: isPie,
                            position: "bottom",
                            labels: { boxWidth: 12, padding: 12 },
                        },
                    },
                    scales: isPie
                        ? {}
                        : { y: { beginAtZero: true, ticks: { callback: (v) => this.fmtCompact(v) } } },
                },
            });
        });
    }

    _mkChart(refKey, config) {
        const ref = this.refs[refKey];
        if (!ref || !ref.el) return;
        if (this.charts[refKey]) this.charts[refKey].destroy();
        this.charts[refKey] = new window.Chart(ref.el.getContext("2d"), config);
    }

    _propertyStateDonut() {
        const rows = orderBy(this.state.data.property_state, PROPERTY_STATE_ORDER);
        this._mkChart("propertyState", {
            type: "doughnut",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.value),
                    backgroundColor: rows.map((r) => r.color),
                    borderWidth: 2,
                    borderColor: "#fff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.label}: ${ctx.parsed} units`,
                        },
                    },
                },
            },
        });
    }

    _propertyTypeDonut() {
        const rows = this.state.data.property_type;
        const palette = ["#6366F1", "#10B981", "#F59E0B", "#EF4444", "#3B82F6", "#8B5CF6"];
        this._mkChart("propertyType", {
            type: "polarArea",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.value),
                    backgroundColor: rows.map((_r, i) => palette[i % palette.length] + "CC"),
                    borderColor: rows.map((_r, i) => palette[i % palette.length]),
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
                },
            },
        });
    }

    _projectInventoryStacked() {
        const rows = this.state.data.project_inventory.slice(0, 10);
        this._mkChart("projectInventory", {
            type: "bar",
            data: {
                labels: rows.map((r) => r.name),
                datasets: [
                    { label: "Available", data: rows.map((r) => r.available), backgroundColor: "#10B981", stack: "s" },
                    { label: "Reserved",  data: rows.map((r) => r.reserved),  backgroundColor: "#F59E0B", stack: "s" },
                    { label: "Booked",    data: rows.map((r) => r.booked),    backgroundColor: "#3B82F6", stack: "s" },
                    { label: "Sold",      data: rows.map((r) => r.sold),      backgroundColor: "#6366F1", stack: "s" },
                    { label: "Blocked",   data: rows.map((r) => r.blocked),   backgroundColor: "#EF4444", stack: "s" },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: "y",
                scales: {
                    x: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
                    y: { stacked: true },
                },
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
                },
            },
        });
    }

    _bookingStateDonut() {
        const rows = orderBy(this.state.data.booking_state, BOOKING_STATE_ORDER);
        this._mkChart("bookingState", {
            type: "doughnut",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.value),
                    backgroundColor: rows.map((r) => r.color),
                    borderWidth: 2,
                    borderColor: "#fff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const r = rows[ctx.dataIndex];
                                return `${r.label}: ${r.value} (${this.fmtCompactMoney(r.amount)})`;
                            },
                        },
                    },
                },
            },
        });
    }

    _bookingTrendLine() {
        const rows = this.state.data.booking_trend;
        this._mkChart("bookingTrend", {
            type: "line",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [
                    {
                        label: "Bookings",
                        data: rows.map((r) => r.count),
                        borderColor: "#6366F1",
                        backgroundColor: "rgba(99,102,241,0.15)",
                        fill: true,
                        tension: 0.35,
                        yAxisID: "y",
                        pointRadius: 3,
                        pointHoverRadius: 6,
                    },
                    {
                        label: "Booking Value",
                        data: rows.map((r) => r.value),
                        borderColor: "#10B981",
                        backgroundColor: "rgba(16,185,129,0.15)",
                        fill: false,
                        tension: 0.35,
                        yAxisID: "y1",
                        pointRadius: 3,
                        pointHoverRadius: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Count" } },
                    y1: {
                        beginAtZero: true,
                        position: "right",
                        grid: { drawOnChartArea: false },
                        title: { display: true, text: "Value" },
                        ticks: { callback: (v) => this.fmtCompact(v) },
                    },
                },
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                if (ctx.dataset.yAxisID === "y1") {
                                    return `${ctx.dataset.label}: ${this.fmtCompactMoney(ctx.parsed.y)}`;
                                }
                                return `${ctx.dataset.label}: ${ctx.parsed.y}`;
                            },
                        },
                    },
                },
            },
        });
    }

    _installmentStateDonut() {
        const rows = orderBy(this.state.data.installment_state, INSTALLMENT_STATE_ORDER);
        this._mkChart("installmentState", {
            type: "doughnut",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.value),
                    backgroundColor: rows.map((r) => r.color),
                    borderWidth: 2,
                    borderColor: "#fff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const r = rows[ctx.dataIndex];
                                return `${r.label}: ${r.value}  •  Outstanding ${this.fmtCompactMoney(r.residual)}`;
                            },
                        },
                    },
                },
            },
        });
    }

    _agingBar() {
        const rows = this.state.data.aging;
        this._mkChart("aging", {
            type: "bar",
            data: {
                labels: rows.map((r) => `${r.label} days`),
                datasets: [
                    {
                        label: "Installments",
                        data: rows.map((r) => r.count),
                        backgroundColor: rows.map((r) => r.color),
                        borderRadius: 6,
                        yAxisID: "y",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Count" } },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const r = rows[ctx.dataIndex];
                                return `${r.count} installment(s)  •  ${this.fmtCompactMoney(r.amount)} outstanding`;
                            },
                        },
                    },
                },
            },
        });
    }

    _collectionTrendBar() {
        const rows = this.state.data.collection_trend;
        this._mkChart("collectionTrend", {
            type: "bar",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [
                    {
                        label: "Due",
                        data: rows.map((r) => r.due),
                        backgroundColor: "rgba(148,163,184,0.6)",
                        borderRadius: 6,
                    },
                    {
                        label: "Collected",
                        data: rows.map((r) => r.collected),
                        backgroundColor: "#10B981",
                        borderRadius: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { callback: (v) => this.fmtCompact(v) },
                    },
                },
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${this.fmtCompactMoney(ctx.parsed.y)}`,
                        },
                    },
                },
            },
        });
    }

    _receivableVsReceivedBar() {
        const rows = this.state.data.receivable_vs_received || [];
        this._mkChart("receivableVsReceived", {
            type: "bar",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [
                    {
                        label: "Received",
                        data: rows.map((r) => r.received),
                        backgroundColor: "#10B981",
                        borderRadius: 6,
                        stack: "s",
                    },
                    {
                        label: "Receivable (Outstanding)",
                        data: rows.map((r) => r.receivable),
                        backgroundColor: "#F59E0B",
                        borderRadius: 6,
                        stack: "s",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        ticks: { callback: (v) => this.fmtCompact(v) },
                    },
                },
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const r = rows[ctx.dataIndex];
                                const rate = r.total ? Math.round((r.received / r.total) * 100) : 0;
                                if (ctx.dataset.label === "Received") {
                                    return `Received: ${this.fmtCompactMoney(r.received)} (${rate}%)`;
                                }
                                return `Receivable: ${this.fmtCompactMoney(r.receivable)}`;
                            },
                        },
                    },
                },
            },
        });
    }

    _transferStateDonut() {
        const rows = orderBy(this.state.data.transfer_state, TRANSFER_STATE_ORDER);
        this._mkChart("transferState", {
            type: "doughnut",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    data: rows.map((r) => r.value),
                    backgroundColor: rows.map((r) => r.color),
                    borderWidth: 2,
                    borderColor: "#fff",
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const r = rows[ctx.dataIndex];
                                return `${r.label}: ${r.value}  •  ${this.fmtCompactMoney(r.amount)}`;
                            },
                        },
                    },
                },
            },
        });
    }

    _transferTaxBar() {
        const rows = this.state.data.transfer_tax_breakdown;
        this._mkChart("transferTax", {
            type: "bar",
            data: {
                labels: rows.map((r) => r.label),
                datasets: [{
                    label: "Tax Collected",
                    data: rows.map((r) => r.amount),
                    backgroundColor: "#6366F1",
                    borderRadius: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: "y",
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { callback: (v) => this.fmtCompact(v) },
                    },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => this.fmtCompactMoney(ctx.parsed.x),
                        },
                    },
                },
            },
        });
    }
}

registry.category("actions").add("sa_property_dashboard", SaPropertyDashboard);
