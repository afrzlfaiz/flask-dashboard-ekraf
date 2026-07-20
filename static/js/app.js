/**
 * app.js — Core application logic: navigation, filters, toast, init.
 * Multi-select filters use Tom Select (vanilla JS, Bootstrap 5 themed).
 */

// Tom Select instances
let tsKecamatan, tsKelurahan, tsSubsektor;
let toastTimer = null;
let resizeTimer = null;

const tsBaseConfig = (placeholder) => ({
    placeholder,
    closeAfterSelect: false,
    maxItems: null,
    plugins: {
        remove_button: { title: "Hapus" },
    },
    render: {
        no_results: () => '<div class="no-results px-3 py-2 text-muted small">Tidak ditemukan</div>',
    },
});

const App = {
    currentPage: "overview-page",
    currentFilter: { kecamatan: [], kelurahan: [], subsektor: [], search: "" },

    escapeHTML(value) {
        return String(value ?? "").replace(/[&<>'"]/g, char => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "'": "&#39;",
            '"': "&quot;",
        })[char]);
    },

    // ── Toast ─────────────────────────────────────────
    showToast(title, message) {
        const toast = document.getElementById("custom-toast");
        document.getElementById("toast-title").textContent = title;
        document.getElementById("toast-message").textContent = message;
        window.clearTimeout(toastTimer);
        toast.classList.add("show");
        toastTimer = window.setTimeout(() => toast.classList.remove("show"), 3200);
    },

    setSidebar(open) {
        const sidebar = document.getElementById("sidebar");
        const backdrop = document.getElementById("sidebar-backdrop");
        const toggle = document.getElementById("sidebar-toggle");
        const shouldOpen = Boolean(open) && window.innerWidth < 992;

        sidebar.classList.toggle("show", shouldOpen);
        backdrop.classList.toggle("show", shouldOpen);
        document.body.classList.toggle("sidebar-open", shouldOpen);
        toggle.setAttribute("aria-expanded", String(shouldOpen));

        if (shouldOpen) {
            window.setTimeout(() => document.getElementById("sidebar-close")?.focus(), 220);
        }
    },

    resizeVisuals() {
        if (typeof MainMap !== "undefined" && MainMap) MainMap.invalidateSize({ pan: false });
        if (typeof DensityMap !== "undefined" && DensityMap) DensityMap.invalidateSize({ pan: false });
        if (typeof DBScanMap !== "undefined" && DBScanMap) DBScanMap.invalidateSize({ pan: false });

        if (window.Plotly) {
            ["kecamatan-donut-chart", "subsektor-bar-chart"].forEach(id => {
                const chart = document.getElementById(id);
                if (chart && chart.offsetParent !== null && chart.data) Plotly.Plots.resize(chart);
            });
        }
    },

    // ── Navigation ────────────────────────────────────
    switchPage(targetId, updateState = true) {
        if (targetId !== "overview-page" &&
            typeof DensityMap !== "undefined" && DensityMap &&
            typeof densityHeatLayer !== "undefined" && densityHeatLayer) {
            DensityMap.removeLayer(densityHeatLayer);
            densityHeatLayer = null;
        }
        document.querySelectorAll(".page-view").forEach(v => v.classList.add("d-none"));
        document.querySelectorAll(".menu-item").forEach(m => {
            m.classList.remove("active");
            m.removeAttribute("aria-current");
        });

        const target = document.getElementById(targetId);
        if (target) target.classList.remove("d-none");

        const link = document.querySelector(`.menu-item[data-target="${targetId}"]`);
        if (link) {
            link.classList.add("active");
            link.setAttribute("aria-current", "page");
        }

        App.currentPage = targetId;

        if (updateState) {
            const pathMap = {
                "overview-page": "/",
                "dbscan-page": "/clustering",
                "table-page": "/tabel",
                "manage-page": "/kelola",
                "tentang-page": "/tentang"
            };
            const path = pathMap[targetId] || "/";
            if (window.location.pathname !== path) {
                window.history.pushState(null, "", path);
            }
        }

        setTimeout(() => {
            App.resizeVisuals();

            if (targetId === "dbscan-page") {
                const clusterLayer = typeof initDBScanMap === "function" ? initDBScanMap() : null;
                if (clusterLayer && typeof DBScanMap !== "undefined" && DBScanMap) {
                    DBScanMap.invalidateSize();
                    if (typeof runDBSCAN === "function") runDBSCAN();
                }
            }

            if (targetId === "overview-page") {
                if (typeof refreshOverview === "function") refreshOverview();
            }

            if (targetId === "table-page" &&
                typeof dataTableInstance !== "undefined" && dataTableInstance) {
                dataTableInstance.columns.adjust();
                if (dataTableInstance.responsive) dataTableInstance.responsive.recalc();
            }
        }, 250);

        App.setSidebar(false);
        window.scrollTo({ top: 0, behavior: "smooth" });
    },

    // ── Filters ───────────────────────────────────────
    getFilterParams() {
        return {
            kecamatan: tsKecamatan?.items || [],
            kelurahan: tsKelurahan?.items || [],
            subsektor: tsSubsektor?.items || [],
            search: document.getElementById("filter-search").value,
        };
    },

    buildFilterQuery() {
        const p = App.getFilterParams();
        const params = new URLSearchParams();
        p.kecamatan.forEach(v => params.append("kecamatan", v));
        p.kelurahan.forEach(v => params.append("kelurahan", v));
        p.subsektor.forEach(v => params.append("subsektor", v));
        if (p.search) params.set("search", p.search);
        return params.toString();
    },

    async applyFilters() {
        App.currentFilter = App.getFilterParams();
        const applyButton = document.getElementById("btn-apply-filter");
        const refreshButton = document.getElementById("btn-refresh-data");
        applyButton.disabled = true;
        refreshButton.disabled = true;
        refreshButton.classList.add("is-loading");

        try {
            const kpiResp = await fetch(`/api/kpi?${App.buildFilterQuery()}`);
            if (!kpiResp.ok) throw new Error(`Server merespons ${kpiResp.status}`);
            const kpi = await kpiResp.json();
            document.getElementById("kpi-total-pelaku").textContent = kpi.total_pelaku.toLocaleString("id-ID");
            document.getElementById("kpi-kecamatan").textContent = kpi.total_kecamatan;
            document.getElementById("kpi-kelurahan").textContent = kpi.total_kelurahan;
            document.getElementById("kpi-subsektor").textContent = kpi.total_subsektor;
            document.getElementById("kpi-valid").textContent = kpi.total_valid.toLocaleString("id-ID");
            document.getElementById("active-count").textContent = kpi.total_pelaku.toLocaleString("id-ID");

            if (typeof refreshOverview === "function") refreshOverview();
            if (typeof refreshTable === "function") refreshTable();
            if (typeof refreshKelolaList === "function") refreshKelolaList();

            App.showToast("Sukses", `Menampilkan ${kpi.total_pelaku} data pelaku.`);

            if (window.innerWidth < 992 && window.bootstrap) {
                const filterBody = document.getElementById("filter-body");
                bootstrap.Collapse.getOrCreateInstance(filterBody, { toggle: false }).hide();
            }
        } catch (err) {
            App.showToast("Error", "Gagal memuat data: " + err.message);
        } finally {
            applyButton.disabled = false;
            refreshButton.disabled = false;
            refreshButton.classList.remove("is-loading");
        }
    },

    async resetFilters() {
        tsKecamatan?.clear(true);
        tsSubsektor?.clear(true);
        document.getElementById("filter-search").value = "";

        // Rebuild kelurahan with full options
        tsKelurahan?.destroy();
        const kelSel = document.getElementById("filter-kelurahan");
        kelSel.innerHTML = '<option value="">Semua Kelurahan</option>';

        try {
            const response = await fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
            const result = await response.json();
            const opts = result.options?.kelurahan || [];
            opts.forEach(k => kelSel.add(new Option(k, k)));
        } catch (err) {
            console.error("Failed to reset kelurahan options:", err);
        } finally {
            tsKelurahan = new TomSelect("#filter-kelurahan", tsBaseConfig("Semua Kelurahan"));
            await App.applyFilters();
        }
    },

    // ── Init dropdowns ─────────────────────────────────
    async loadDropdownOptions() {
        try {
            const resp = await fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
            const result = await resp.json();
            const opts = result.options || {};

            // Kecamatan
            const kecSel = document.getElementById("filter-kecamatan");
            opts.kecamatan?.forEach(k => kecSel.add(new Option(k, k)));
            tsKecamatan = new TomSelect("#filter-kecamatan", tsBaseConfig("Semua Kecamatan"));

            // Subsektor
            const subSel = document.getElementById("filter-subsektor");
            opts.subsektor?.forEach(s => subSel.add(new Option(s, s)));
            tsSubsektor = new TomSelect("#filter-subsektor", tsBaseConfig("Semua Subsektor"));

            // Kelurahan
            const kelSel = document.getElementById("filter-kelurahan");
            opts.kelurahan?.forEach(k => kelSel.add(new Option(k, k)));
            tsKelurahan = new TomSelect("#filter-kelurahan", tsBaseConfig("Semua Kelurahan"));

            // CRUD form selects (plain, no Tom Select)
            const crudKec = document.getElementById("crud-kecamatan");
            opts.kecamatan?.forEach(k => crudKec.add(new Option(k, k)));

            const crudSub = document.getElementById("crud-subsektor");
            opts.subsektor?.forEach(s => crudSub.add(new Option(s, s)));

            document.getElementById("total-count").textContent = (result.total_db || 0).toLocaleString("id-ID");
        } catch (err) {
            console.error("Failed to load dropdowns:", err);
        }
    },
};

// ── DOM Ready ────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // Clock
    const updateClock = () => {
        const now = new Date();
        document.getElementById("live-time-badge").innerHTML =
            `<i class="bi bi-clock me-1 text-primary"></i> ${now.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" })}, ${now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}`;
    };
    updateClock();
    setInterval(updateClock, 30000);

    // Sidebar
    document.querySelectorAll(".menu-item").forEach(link => {
        link.addEventListener("click", function (e) {
            e.preventDefault();
            App.switchPage(this.getAttribute("data-target"));
        });
    });
    document.getElementById("sidebar-toggle").addEventListener("click", () => {
        App.setSidebar(!document.getElementById("sidebar").classList.contains("show"));
    });
    document.getElementById("sidebar-close").addEventListener("click", () => App.setSidebar(false));
    document.getElementById("sidebar-backdrop").addEventListener("click", () => App.setSidebar(false));

    document.addEventListener("keydown", event => {
        if (event.key === "Escape") App.setSidebar(false);
    });

    // Buttons
    document.getElementById("btn-apply-filter").addEventListener("click", () => App.applyFilters());
    document.getElementById("btn-reset-filter").addEventListener("click", () => App.resetFilters());
    document.getElementById("btn-refresh-data").addEventListener("click", () => {
        App.applyFilters();
    });
    document.getElementById("filter-search").addEventListener("keydown", event => {
        if (event.key === "Enter") {
            event.preventDefault();
            App.applyFilters();
        }
    });

    window.addEventListener("resize", () => {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(() => {
            if (window.innerWidth >= 992) App.setSidebar(false);
            App.resizeVisuals();
        }, 160);
    });

    // Kecamatan change → rebuild kelurahan options
    tsKecamatan_onChange = function () {
        const selected = tsKecamatan?.items || [];
        const prevSelected = tsKelurahan?.items || [];

        tsKelurahan.destroy();
        const kelSel = document.getElementById("filter-kelurahan");
        kelSel.innerHTML = '<option value="">Semua Kelurahan</option>';

        const body = selected.length ? { kecamatan: selected } : {};
        fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
            .then(r => r.json())
            .then(result => {
                (result.options?.kelurahan || []).forEach(k => {
                    kelSel.add(new Option(k, k));
                });
                tsKelurahan = new TomSelect("#filter-kelurahan", tsBaseConfig("Semua Kelurahan"));
                tsKelurahan.setValue(prevSelected.filter(v => {
                    return Array.from(kelSel.options).some(o => o.value === v);
                }));
            })
            .catch(() => {
                tsKelurahan = new TomSelect("#filter-kelurahan", tsBaseConfig("Semua Kelurahan"));
            });
    };

    // CRUD kecamatan → kelurahan (plain select)
    document.getElementById("crud-kecamatan").addEventListener("change", async function () {
        const kec = this.value;
        const kelSel = document.getElementById("crud-kelurahan");
        kelSel.innerHTML = '<option value="">Pilih...</option>';
        if (kec) {
            try {
                const resp = await fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kecamatan: kec }) });
                const result = await resp.json();
                result.options?.kelurahan?.forEach(k => {
                    kelSel.add(new Option(k, k));
                });
            } catch (e) { /* ignore */ }
        }
    });

    // Popstate navigation listener
    window.addEventListener("popstate", () => {
        const path = window.location.pathname;
        const pathMap = {
            "/clustering": "dbscan-page",
            "/tabel": "table-page",
            "/kelola": "manage-page",
            "/tentang": "tentang-page"
        };
        App.switchPage(pathMap[path] || "overview-page", false);
    });

    // Init
    App.loadDropdownOptions().then(() => {
        // Wire kecamatan onChange AFTER Tom Select instances are created
        tsKecamatan.on("change", tsKecamatan_onChange);
        App.applyFilters();

        const initialPath = window.location.pathname;
        const pathMap = {
            "/clustering": "dbscan-page",
            "/tabel": "table-page",
            "/kelola": "manage-page",
            "/tentang": "tentang-page"
        };
        App.switchPage(pathMap[initialPath] || "overview-page", false);
    });
});
