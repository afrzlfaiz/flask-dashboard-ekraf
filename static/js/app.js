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

const tsLocationConfig = (locations) => {
    const config = tsBaseConfig("Semua Lokasi");
    const kecamatan = [...new Set(locations.map(location => location.kecamatan))];
    const options = locations.map(location => ({
        ...location,
        value: `${location.kecamatan}\u001f${location.kelurahan}`,
    }));

    return {
        ...config,
        valueField: "value",
        labelField: "kelurahan",
        searchField: ["kelurahan", "kecamatan"],
        optgroupField: "kecamatan",
        options,
        optgroups: kecamatan.map(value => ({ value, label: value })),
        render: {
            ...config.render,
            optgroup_header: (data, escape) =>
                `<div class="optgroup-header"><i class="bi bi-geo-alt-fill" aria-hidden="true"></i>${escape(data.label)}</div>`,
        },
    };
};

const App = {
    currentPage: "overview-page",
    currentFilter: { kecamatan: [], kelurahan: [], subsektor: [], search: "" },
    malangDistricts: [],

    loadScript(src) {
        const existing = document.querySelector(`script[src="${src}"]`);
        if (existing) return existing.dataset.loaded === "true"
            ? Promise.resolve()
            : new Promise((resolve, reject) => {
                existing.addEventListener("load", resolve, { once: true });
                existing.addEventListener("error", reject, { once: true });
            });
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = src;
            script.onload = () => { script.dataset.loaded = "true"; resolve(); };
            script.onerror = () => reject(new Error(`Gagal memuat ${src}`));
            document.head.appendChild(script);
        });
    },

    loadStyle(href) {
        if (document.querySelector(`link[href="${href}"]`)) return;
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = href;
        document.head.appendChild(link);
    },

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
    switchPage(targetId, updateState = true, refreshData = true) {
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

            if (refreshData && targetId === "overview-page") {
                if (typeof refreshOverview === "function") refreshOverview();
            }

            if (targetId === "table-page" && typeof ensureTablePage === "function") {
                ensureTablePage().then(() => {
                    dataTableInstance?.columns.adjust();
                    dataTableInstance?.responsive?.recalc();
                }).catch(err => App.showToast("Error", err.message));
            }

            if (refreshData && targetId === "manage-page" && typeof refreshKelolaList === "function") {
                refreshKelolaList();
            }
        }, 250);

        App.setSidebar(false);
        window.scrollTo({ top: 0, behavior: "smooth" });
    },

    // ── Filters ───────────────────────────────────────
    getFilterParams() {
        const selectedLocations = (tsKelurahan?.items || [])
            .map(value => tsKelurahan.options[value])
            .filter(Boolean);

        return {
            kecamatan: selectedLocations.length
                ? [...new Set(selectedLocations.map(location => location.kecamatan))]
                : (tsKecamatan?.items || []),
            kelurahan: selectedLocations.map(location => location.kelurahan),
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

    setLocationOptions(locations, selected = []) {
        tsKelurahan?.destroy();
        document.getElementById("filter-kelurahan").innerHTML = "";
        tsKelurahan = new TomSelect("#filter-kelurahan", tsLocationConfig(locations));

        const available = new Set(
            locations.map(location => `${location.kecamatan}\u001f${location.kelurahan}`)
        );
        tsKelurahan.setValue(selected.filter(value => available.has(value)), true);
    },

    syncMalangButton() {
        const selected = new Set(tsKecamatan?.items || []);
        const active = App.malangDistricts.length === 5
            && selected.size === 5
            && App.malangDistricts.every(kecamatan => selected.has(kecamatan));
        const button = document.getElementById("btn-filter-malang");
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
    },

    async applyMalangFilter() {
        if (App.malangDistricts.length !== 5) return;

        const button = document.getElementById("btn-filter-malang");
        const previousLocations = tsKelurahan?.items || [];
        button.disabled = true;

        try {
            tsKecamatan.setValue(App.malangDistricts, true);
            App.syncMalangButton();
            const response = await fetch("/api/filter", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ kecamatan: App.malangDistricts }),
            });
            if (!response.ok) throw new Error(`Server merespons ${response.status}`);
            const result = await response.json();
            App.setLocationOptions(result.options?.lokasi || [], previousLocations);
            await App.applyFilters();
        } catch (err) {
            App.showToast("Error", "Gagal menerapkan filter Kota Malang: " + err.message);
        } finally {
            button.disabled = false;
        }
    },

    async applyFilters() {
        App.currentFilter = App.getFilterParams();
        if (typeof clearOptimalDBSCANResults === "function") clearOptimalDBSCANResults();
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

            if (App.currentPage === "overview-page" && typeof refreshOverview === "function") refreshOverview();
            if (App.currentPage === "table-page" && typeof ensureTablePage === "function") await ensureTablePage();
            if (App.currentPage === "manage-page" && typeof refreshKelolaList === "function") refreshKelolaList();

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
        App.syncMalangButton();
        document.getElementById("filter-search").value = "";

        try {
            const response = await fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
            const result = await response.json();
            App.setLocationOptions(result.options?.lokasi || []);
        } catch (err) {
            console.error("Failed to reset location options:", err);
        }
        await App.applyFilters();
    },

    // ── Init dropdowns ─────────────────────────────────
    async loadDropdownOptions() {
        try {
            const resp = await fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
            const result = await resp.json();
            const opts = result.options || {};
            App.malangDistricts = opts.kota_malang || [];

            // Kecamatan
            const kecSel = document.getElementById("filter-kecamatan");
            opts.kecamatan?.forEach(k => kecSel.add(new Option(k, k)));
            tsKecamatan = new TomSelect("#filter-kecamatan", tsBaseConfig("Semua Kecamatan"));
            document.getElementById("btn-filter-malang").disabled = App.malangDistricts.length !== 5;

            // Subsektor
            const subSel = document.getElementById("filter-subsektor");
            opts.subsektor?.forEach(s => subSel.add(new Option(s, s)));
            tsSubsektor = new TomSelect("#filter-subsektor", tsBaseConfig("Semua Subsektor"));

            // Lokasi: kelurahan dikelompokkan berdasarkan kecamatan
            App.setLocationOptions(opts.lokasi || []);

            // CRUD form suggestions; inputs still accept new values.
            const crudKecList = document.getElementById("crud-kecamatan-options");
            opts.kecamatan?.forEach(k => {
                const option = document.createElement("option");
                option.value = k;
                crudKecList.appendChild(option);
            });

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
    document.getElementById("btn-filter-malang").addEventListener("click", () => App.applyMalangFilter());
    document.getElementById("btn-reset-filter").addEventListener("click", () => App.resetFilters());
    document.getElementById("btn-refresh-data").addEventListener("click", () => {
        App.applyFilters();
    });
    const filterSearch = document.getElementById("filter-search");
    filterSearch.addEventListener("focus", () => filterSearch.removeAttribute("readonly"), { once: true });
    filterSearch.addEventListener("keydown", event => {
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

    // Kecamatan change → rebuild grouped location options
    tsKecamatan_onChange = function () {
        const selected = tsKecamatan?.items || [];
        const prevSelected = tsKelurahan?.items || [];
        App.syncMalangButton();

        const body = selected.length ? { kecamatan: selected } : {};
        fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
            .then(r => r.json())
            .then(result => {
                App.setLocationOptions(result.options?.lokasi || [], prevSelected);
            })
            .catch(() => {
                App.setLocationOptions([], prevSelected);
            });
    };

    // CRUD kecamatan → kelurahan suggestions
    document.getElementById("crud-kecamatan").addEventListener("change", async function () {
        const kec = this.value;
        const kelList = document.getElementById("crud-kelurahan-options");
        kelList.innerHTML = "";
        if (kec) {
            try {
                const resp = await fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kecamatan: kec }) });
                const result = await resp.json();
                result.options?.kelurahan?.forEach(k => {
                    const option = document.createElement("option");
                    option.value = k;
                    kelList.appendChild(option);
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
        const initialPath = window.location.pathname;
        const pathMap = {
            "/clustering": "dbscan-page",
            "/tabel": "table-page",
            "/kelola": "manage-page",
            "/tentang": "tentang-page"
        };
        const initialPage = pathMap[initialPath] || "overview-page";
        App.currentPage = initialPage;
        App.switchPage(initialPage, false, false);
        App.applyFilters();
    });
});
