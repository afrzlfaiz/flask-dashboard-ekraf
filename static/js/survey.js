"use strict";

const SurveyPage = (() => {
    let optionsLoaded = false;
    let optionsPeriodId = null;
    let requestNumber = 0;
    const clusterColors = ["#064b91", "#0e7490", "#d97706", "#64748b", "#7c3aed"];

    const number = value => Number(value || 0).toLocaleString("id-ID");
    const percent = value => `${Number(value || 0).toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;
    const rupiah = value => new Intl.NumberFormat("id-ID", {
        style: "currency", currency: "IDR", maximumFractionDigits: 0,
    }).format(Number(value || 0));
    const escape = value => String(value ?? "").replace(/[&<>'"]/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    })[char]);

    function loadPlotly() {
        const source = "https://cdn.plot.ly/plotly-basic-2.27.0.min.js";
        const existing = document.querySelector(`script[src="${source}"]`);
        if (existing) {
            return window.Plotly ? Promise.resolve() : new Promise((resolve, reject) => {
                existing.addEventListener("load", resolve, { once: true });
                existing.addEventListener("error", reject, { once: true });
            });
        }
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = source;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    function setOptions(selectId, values, placeholder) {
        const select = document.getElementById(selectId);
        if (!select) return;
        select.innerHTML = `<option value="">${placeholder}</option>`;
        values.forEach(value => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
        });
    }

    function setPeriodOptions(periods, selectedId) {
        const select = document.getElementById("survey-filter-period");
        if (!select) return;
        select.innerHTML = "";
        periods.forEach(period => {
            const option = document.createElement("option");
            option.value = String(period.id);
            option.textContent = `${period.label} · ${number(period.rows)} usaha`;
            select.appendChild(option);
        });
        if (periods.length) {
            const value = String(selectedId || periods[0].id);
            select.value = periods.some(period => String(period.id) === value)
                ? value : String(periods[0].id);
        } else {
            select.innerHTML = '<option value="">Belum ada periode survei</option>';
        }
    }

    function renderPeriods(periods) {
        const body = document.getElementById("survey-period-list-body");
        if (!body) return;
        body.innerHTML = periods.length ? periods.map(period => `
            <tr>
                <td><strong>${escape(period.survey_year)}</strong></td>
                <td>${escape(period.label)}</td>
                <td class="text-end">${number(period.rows)}</td>
                <td><span class="badge bg-success-subtle text-success">Aktif</span></td>
            </tr>`).join("") :
            '<tr><td colspan="4" class="text-center text-muted py-3 small">Belum ada periode survei.</td></tr>';
    }

    async function loadOptions() {
        const selectedPeriod = document.getElementById("survey-filter-period")?.value || "";
        if (optionsLoaded && optionsPeriodId === selectedPeriod) return;
        const params = selectedPeriod ? `?period_id=${encodeURIComponent(selectedPeriod)}` : "";
        const response = await fetch(`/api/survey/options${params}`);
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || `Server merespons ${response.status}`);
        setPeriodOptions(result.periods || [], result.selected_period_id || result.default_period_id);
        setOptions("survey-filter-kecamatan", result.options.kecamatan || [], "Semua Kecamatan");
        setOptions("survey-filter-subsektor", result.options.subsektor || [], "Semua Subsektor");
        setOptions("survey-filter-umkm", result.options.klasifikasi_umkm || [], "Semua Klasifikasi");
        setOptions("survey-filter-cluster", result.options.cluster || [], "Semua Cluster");
        renderPeriods(result.periods || []);
        optionsPeriodId = String(result.selected_period_id || result.default_period_id || "");
        optionsLoaded = true;
    }

    function query() {
        const params = new URLSearchParams();
        const values = {
            period_id: document.getElementById("survey-filter-period")?.value || "",
            kecamatan: document.getElementById("survey-filter-kecamatan")?.value || "",
            subsektor: document.getElementById("survey-filter-subsektor")?.value || "",
            klasifikasi_umkm: document.getElementById("survey-filter-umkm")?.value || "",
            cluster: document.getElementById("survey-filter-cluster")?.value || "",
        };
        Object.entries(values).forEach(([key, value]) => { if (value) params.set(key, value); });
        return params.toString();
    }

    function setLoading(loading) {
        ["btn-survey-reset", "btn-survey-apply"].forEach(id => {
            const button = document.getElementById(id);
            if (button) button.disabled = loading;
        });
    }

    function renderKpis(data) {
        const kpi = data.kpi;
        document.getElementById("survey-total-observasi").textContent = number(kpi.total_observasi);
        document.getElementById("survey-total-penjualan").textContent = rupiah(kpi.total_penjualan);
        document.getElementById("survey-median-margin").textContent = percent(kpi.median_margin * 100);
        document.getElementById("survey-total-tenaga-kerja").textContent = number(kpi.total_tenaga_kerja);
        const rate = kpi.total_observasi ? kpi.usaha_tercluster / kpi.total_observasi * 100 : 0;
        document.getElementById("survey-clustered-rate").textContent = percent(rate);
        document.getElementById("survey-source-badge").textContent =
            `${data.source.label || `Survei ${data.source.year}`} · ${number(data.source.rows)} usaha`;
        const model = data.model;
        document.getElementById("survey-model-info").textContent =
            `${model.name} · eps ${model.eps} · min_samples ${model.min_samples} · ` +
            `${model.n_clusters} cluster · silhouette ${model.silhouette?.toFixed(4) || "-"} · noise ${model.noise_percent}%`;
    }

    async function renderCharts(data) {
        if (!data.kpi.total_observasi) {
            ["survey-cluster-chart", "survey-subsector-chart", "survey-kecamatan-chart", "survey-pca-chart"]
                .forEach(id => { document.getElementById(id).innerHTML = '<p class="text-muted text-center py-5">Tidak ada data sesuai filter.</p>'; });
            return;
        }
        await loadPlotly();
        const config = { responsive: true, displayModeBar: false };
        const baseLayout = {
            autosize: true, margin: { l: 12, r: 24, t: 12, b: 42 },
            paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
            font: { family: "Inter", size: 10, color: "#647084" },
        };
        const cluster = data.charts.cluster;
        Plotly.react("survey-cluster-chart", [{
            labels: cluster.labels, values: cluster.values, type: "pie", hole: 0.58,
            marker: { colors: cluster.labels.map((_, i) => clusterColors[i % clusterColors.length]) },
            textinfo: "label+percent", hoverinfo: "label+value+percent",
        }], { ...baseLayout, margin: { l: 8, r: 8, t: 8, b: 58 }, showlegend: true,
            legend: { orientation: "h", x: 0.5, xanchor: "center", y: -0.08, font: { size: 9 } },
            height: 330 }, config);

        const renderBar = (id, chart, color) => Plotly.react(id, [{
            x: chart.values.slice().reverse(), y: chart.labels.slice().reverse(),
            type: "bar", orientation: "h", marker: { color },
            text: chart.values.slice().reverse().map(number), textposition: "outside", cliponaxis: false,
        }], { ...baseLayout, margin: { l: 138, r: 42, t: 12, b: 32 }, height: 330,
            xaxis: { gridcolor: "#edf1f5", zeroline: false, fixedrange: true },
            yaxis: { fixedrange: true, automargin: true } }, config);
        renderBar("survey-subsector-chart", data.charts.subsektor, "#0b5da8");
        renderBar("survey-kecamatan-chart", data.charts.kecamatan, "#0e7490");

        const grouped = {};
        data.pca.forEach(point => {
            (grouped[point.cluster] ||= { x: [], y: [], name: point.cluster }).x.push(point.x);
            grouped[point.cluster].y.push(point.y);
        });
        Plotly.react("survey-pca-chart", Object.values(grouped).map((group, i) => ({
            ...group, mode: "markers", type: "scatter", marker: { size: 7, color: clusterColors[i % clusterColors.length], opacity: 0.7 },
            hovertemplate: `${escape(group.name)}<extra></extra>`,
        })), { ...baseLayout, margin: { l: 50, r: 20, t: 12, b: 48 }, height: 330,
            xaxis: { title: "PC1", gridcolor: "#edf1f5", zeroline: false },
            yaxis: { title: "PC2", gridcolor: "#edf1f5", zeroline: false }, legend: { orientation: "h" } }, config);
    }

    function renderProfiles(data) {
        const container = document.getElementById("survey-cluster-profiles");
        container.innerHTML = data.profiles.length ? data.profiles.map((profile, index) => `
            <div class="col-12 col-md-6 col-xl-4">
                <div class="survey-profile-card h-100" style="border-left-color:${clusterColors[index % clusterColors.length]}">
                    <div class="d-flex align-items-center gap-2 mb-2">
                        <span class="survey-profile-dot" style="background:${clusterColors[index % clusterColors.length]}"></span>
                        <strong>${escape(profile.cluster)}</strong>
                        <span class="badge bg-secondary ms-auto">${number(profile.jumlah_usaha)} usaha</span>
                    </div>
                    <div class="small text-primary fw-semibold mb-2">${escape(profile.tipologi_usaha)}</div>
                    <div class="survey-profile-metrics">
                        <span>Median penjualan <strong>${rupiah(profile.penjualan_tahunan)}</strong></span>
                        <span>Median margin <strong>${percent(profile.margin_profit * 100)}</strong></span>
                        <span>Tenaga kerja <strong>${number(profile.tenaga_kerja)}</strong></span>
                        <span>Tekanan biaya <strong>${percent(profile.tekanan_biaya_terpilih * 100)}</strong></span>
                    </div>
                    <p class="small text-muted mb-0 mt-2">${escape(profile.arah_kebijakan)}</p>
                </div>
            </div>`).join("") : '<div class="col-12 text-muted">Tidak ada data pada filter ini.</div>';
    }

    function renderDistrictTable(data) {
        const body = document.getElementById("survey-kecamatan-table-body");
        body.innerHTML = data.kecamatan_summary.length ? data.kecamatan_summary.map(row => `
            <tr><td class="fw-semibold">${escape(row.kecamatan)}</td><td>${number(row.jumlah_usaha)}</td>
            <td>${rupiah(row.total_penjualan)}</td><td>${percent(row.median_margin * 100)}</td>
            <td>${number(row.total_tenaga_kerja)}</td></tr>`).join("") :
            '<tr><td colspan="5" class="text-center text-muted py-3">Tidak ada data sesuai filter.</td></tr>';
    }

    function renderActors(data) {
        const body = document.getElementById("survey-actor-table-body");
        const counter = document.getElementById("survey-actor-count");
        const actors = data.actors || [];
        if (counter) counter.textContent = `${number(actors.length)} pelaku`;
        if (!body) return;
        body.innerHTML = actors.length ? actors.map((actor, index) => {
            const clusterClass = actor.cluster === "Noise"
                ? "bg-warning text-dark"
                : actor.cluster === "Tidak terpetakan" ? "bg-secondary" : "bg-primary";
            const statusClass = actor.status === "Terpetakan" ? "text-success" : "text-muted";
            return `
                <tr>
                    <td>${index + 1}</td>
                    <td><strong>${escape(actor.nama_usaha)}</strong><div class="small text-muted">Baris survei ${number(actor.row_number)}</div></td>
                    <td>${escape(actor.subsektor)}</td>
                    <td>${escape(actor.kelurahan)}, ${escape(actor.kecamatan)}</td>
                    <td>${escape(actor.klasifikasi_umkm)}</td>
                    <td><span class="badge ${clusterClass}">${escape(actor.cluster)}</span></td>
                    <td class="${statusClass}">${escape(actor.status)}</td>
                </tr>`;
        }).join("") :
            '<tr><td colspan="7" class="text-center text-muted py-3">Tidak ada pelaku sesuai filter.</td></tr>';
    }

    async function importSurveyYear() {
        const yearInput = document.getElementById("survey-year-input");
        const fileInput = document.getElementById("survey-year-file");
        const alertBox = document.getElementById("survey-period-alert");
        const year = Number.parseInt(yearInput?.value || "", 10);
        const file = fileInput?.files?.[0];
        const showAlert = (type, message) => {
            alertBox.className = `alert alert-${type} mt-3 mb-3 py-2 small`;
            alertBox.textContent = message;
            alertBox.classList.remove("d-none");
        };

        if (!Number.isInteger(year) || year < 2026 || year > 2100) {
            showAlert("danger", "Masukkan tahun survei antara 2026 dan 2100.");
            return;
        }
        if (!file || !file.name.toLowerCase().endsWith(".xlsx")) {
            showAlert("danger", "Pilih file survei dengan format XLSX.");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showAlert("danger", "Ukuran file survei melebihi 10 MB.");
            return;
        }

        const button = document.getElementById("btn-import-survey-year");
        button.disabled = true;
        alertBox.classList.add("d-none");
        try {
            const formData = new FormData();
            formData.append("survey_year", String(year));
            formData.append("sheet_name", document.getElementById("survey-year-sheet-name")?.textContent || "Sheet6");
            formData.append("file", file);
            const response = await fetch("/api/survey/import", {
                method: "POST",
                headers: { "X-CSRFToken": document.querySelector('meta[name="csrf-token"]')?.content || "" },
                body: formData,
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || "Import survei gagal.");
            showAlert("success", result.message);
            fileInput.value = "";
            optionsLoaded = false;
            optionsPeriodId = null;
            await refresh();
        } catch (error) {
            showAlert("danger", error.message);
        } finally {
            button.disabled = false;
        }
    }

    async function refresh() {
        const currentRequest = ++requestNumber;
        setLoading(true);
        const errorBox = document.getElementById("survey-error");
        errorBox.classList.add("d-none");
        try {
            await loadOptions();
            const response = await fetch(`/api/survey/summary?${query()}`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.message || `Server merespons ${response.status}`);
            if (currentRequest !== requestNumber) return;
            renderKpis(data);
            renderProfiles(data);
            renderActors(data);
            renderDistrictTable(data);
            await renderCharts(data);
        } catch (error) {
            errorBox.textContent = `Data survei belum dapat dimuat: ${error.message}`;
            errorBox.classList.remove("d-none");
        } finally {
            setLoading(false);
        }
    }

    function reset() {
        const period = document.getElementById("survey-filter-period");
        if (period?.options.length) period.value = period.options[0].value;
        ["survey-filter-kecamatan", "survey-filter-subsektor", "survey-filter-umkm", "survey-filter-cluster"].forEach(id => {
            const select = document.getElementById(id);
            if (select) select.value = "";
        });
        optionsLoaded = false;
        optionsPeriodId = null;
        refresh();
    }

    function init() {
        document.getElementById("btn-survey-apply")?.addEventListener("click", refresh);
        document.getElementById("btn-survey-reset")?.addEventListener("click", reset);
        document.getElementById("btn-refresh-data")?.addEventListener("click", refresh);
        document.getElementById("btn-import-survey-year")?.addEventListener("click", importSurveyYear);
        document.getElementById("survey-filter-period")?.addEventListener("change", () => {
            ["survey-filter-kecamatan", "survey-filter-subsektor", "survey-filter-umkm", "survey-filter-cluster"].forEach(id => {
                const select = document.getElementById(id);
                if (select) select.value = "";
            });
            optionsLoaded = false;
            optionsPeriodId = null;
            refresh();
        });
        if (document.body.classList.contains("survey-standalone")) {
            setupStandaloneHeader();
            refresh();
        }
    }

    function invalidateOptions() {
        optionsLoaded = false;
        optionsPeriodId = null;
    }

    function setupStandaloneHeader() {
        const clock = document.getElementById("live-time-badge");
        if (clock) {
            const updateClock = () => {
                const now = new Date();
                clock.innerHTML = `<i class="bi bi-clock me-1 text-primary"></i> ${now.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" })}, ${now.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })}`;
            };
            updateClock();
            window.setInterval(updateClock, 30000);
        }
    }

    return { init, refresh, invalidateOptions };
})();

function refreshSurvey() {
    return SurveyPage.refresh();
}

document.addEventListener("DOMContentLoaded", () => SurveyPage.init());
