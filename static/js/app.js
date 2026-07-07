/**
 * app.js — Core application logic: navigation, filters, toast, init.
 * Multi-select filters use Tom Select (vanilla JS, Bootstrap 5 themed).
 */

// Tom Select instances
let tsKecamatan, tsKelurahan, tsSubsektor;

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

    // ── Toast ─────────────────────────────────────────
    showToast(title, message) {
        const toast = document.getElementById("custom-toast");
        document.getElementById("toast-title").textContent = title;
        document.getElementById("toast-message").textContent = message;
        toast.style.display = "block";
        setTimeout(() => { toast.style.transform = "translateY(0)"; }, 50);
        setTimeout(() => {
            toast.style.transform = "translateY(20px)";
            setTimeout(() => { toast.style.display = "none"; }, 300);
        }, 3000);
    },

    // ── Navigation ────────────────────────────────────
    switchPage(targetId, updateState = true) {
        document.querySelectorAll(".page-view").forEach(v => v.classList.add("d-none"));
        document.querySelectorAll(".menu-item").forEach(m => m.classList.remove("active"));

        const target = document.getElementById(targetId);
        if (target) target.classList.remove("d-none");

        const link = document.querySelector(`.menu-item[data-target="${targetId}"]`);
        if (link) link.classList.add("active");

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
            if (window.MainMap) MainMap.invalidateSize();
            if (window.DensityMap) DensityMap.invalidateSize();

            if (targetId === "dbscan-page") {
                if (!window.DBScanMap && typeof initDBScanMap === "function") initDBScanMap();
                if (window.DBScanMap) {
                    DBScanMap.invalidateSize();
                    if (typeof runDBSCAN === "function") runDBSCAN();
                }
            }

            if (targetId === "overview-page" && window.DensityMap) {
                DensityMap.invalidateSize();
                if (typeof updateDensityHeatmap === "function") updateDensityHeatmap();
            }
        }, 250);

        document.getElementById("sidebar").classList.remove("show");
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
        App.showToast("Filter", "Menerapkan filter...");

        try {
            const kpiResp = await fetch(`/api/kpi?${App.buildFilterQuery()}`);
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
        } catch (err) {
            App.showToast("Error", "Gagal memuat data: " + err.message);
        }
    },

    resetFilters() {
        tsKecamatan.clear();
        tsSubsektor.clear();
        document.getElementById("filter-search").value = "";

        // Rebuild kelurahan with full options
        tsKelurahan.destroy();
        const kelSel = document.getElementById("filter-kelurahan");
        kelSel.innerHTML = '<option value="">Semua Kelurahan</option>';

        fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) })
            .then(r => r.json())
            .then(result => {
                const opts = result.options?.kelurahan || [];
                opts.forEach(k => { kelSel.innerHTML += `<option value="${k}">${k}</option>`; });
                tsKelurahan = new TomSelect("#filter-kelurahan", tsBaseConfig("Semua Kelurahan"));
            })
            .catch(() => { tsKelurahan = new TomSelect("#filter-kelurahan", tsBaseConfig("Semua Kelurahan")); });

        App.applyFilters();
    },

    // ── Init dropdowns ─────────────────────────────────
    async loadDropdownOptions() {
        try {
            const resp = await fetch("/api/filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
            const result = await resp.json();
            const opts = result.options || {};

            // Kecamatan
            const kecSel = document.getElementById("filter-kecamatan");
            opts.kecamatan?.forEach(k => { kecSel.innerHTML += `<option value="${k}">${k}</option>`; });
            tsKecamatan = new TomSelect("#filter-kecamatan", tsBaseConfig("Semua Kecamatan"));

            // Subsektor
            const subSel = document.getElementById("filter-subsektor");
            opts.subsektor?.forEach(s => { subSel.innerHTML += `<option value="${s}">${s}</option>`; });
            tsSubsektor = new TomSelect("#filter-subsektor", tsBaseConfig("Semua Subsektor"));

            // Kelurahan
            const kelSel = document.getElementById("filter-kelurahan");
            opts.kelurahan?.forEach(k => { kelSel.innerHTML += `<option value="${k}">${k}</option>`; });
            tsKelurahan = new TomSelect("#filter-kelurahan", tsBaseConfig("Semua Kelurahan"));

            // CRUD form selects (plain, no Tom Select)
            const crudKec = document.getElementById("crud-kecamatan");
            opts.kecamatan?.forEach(k => { crudKec.innerHTML += `<option value="${k}">${k}</option>`; });

            const crudSub = document.getElementById("crud-subsektor");
            opts.subsektor?.forEach(s => { crudSub.innerHTML += `<option value="${s}">${s}</option>`; });

            document.getElementById("total-count").textContent = (result.total_db || 0).toLocaleString("id-ID");
        } catch (err) {
            console.error("Failed to load dropdowns:", err);
        }
    },
};

// ── DOM Ready ────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // Clock
    setInterval(() => {
        const now = new Date();
        document.getElementById("live-time-badge").innerHTML =
            `<i class="bi bi-clock me-1 text-primary"></i> ${now.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" })}, ${now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}`;
    }, 1000);

    // Sidebar
    document.querySelectorAll(".menu-item").forEach(link => {
        link.addEventListener("click", function (e) {
            e.preventDefault();
            App.switchPage(this.getAttribute("data-target"));
        });
    });
    document.getElementById("sidebar-toggle").addEventListener("click", () => {
        document.getElementById("sidebar").classList.add("show");
    });

    // Buttons
    document.getElementById("btn-apply-filter").addEventListener("click", () => App.applyFilters());
    document.getElementById("btn-reset-filter").addEventListener("click", () => App.resetFilters());
    document.getElementById("btn-refresh-data").addEventListener("click", () => {
        App.showToast("Refresh", "Memperbarui data...");
        App.applyFilters();
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
                    kelSel.innerHTML += `<option value="${k}">${k}</option>`;
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
                    kelSel.innerHTML += `<option value="${k}">${k}</option>`;
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
