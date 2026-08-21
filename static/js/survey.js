"use strict";

const SurveyPage = (() => {
    let page = 1;
    let pages = 0;
    let requestNumber = 0;
    let knownClusters = [];

    const root = () => document.getElementById("survey-period-page");
    const year = () => root()?.dataset.periodYear || "";
    const number = value => Number(value || 0).toLocaleString("id-ID");
    const percent = value => `${Number(value || 0).toLocaleString("id-ID", { maximumFractionDigits: 1 })}%`;
    const rupiah = value => {
        const amount = Number(value || 0);
        const absolute = Math.abs(amount);
        const units = absolute >= 1e12 ? [1e12, " T"]
            : absolute >= 1e9 ? [1e9, " M"]
            : absolute >= 1e6 ? [1e6, " jt"]
            : [1, ""];
        const formatted = new Intl.NumberFormat("id-ID", {
            maximumFractionDigits: units[0] === 1 ? 0 : 2,
        }).format(Math.abs(amount) / units[0]);
        return `${amount < 0 ? "-" : ""}Rp${formatted}${units[1]}`;
    };
    const escape = value => String(value ?? "").replace(/[&<>'"]/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    })[char]);

    function setLoading(loading) {
        ["survey-filter-cluster", "btn-refresh-data"]
            .forEach(id => {
                const element = document.getElementById(id);
                if (element) element.disabled = loading;
            });
        const refresh = document.getElementById("btn-refresh-data");
        if (refresh) refresh.classList.toggle("is-loading", loading);
    }

    async function getJson(url) {
        const response = await fetch(url, { headers: { Accept: "application/json" } });
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || `Server merespons ${response.status}`);
        return result;
    }

    function renderClusterOptions(labels) {
        const select = document.getElementById("survey-filter-cluster");
        if (!select) return;
        const selected = select.value;
        select.innerHTML = '<option value="">Semua Cluster/Noise</option>';
        labels.forEach(label => {
            const option = document.createElement("option");
            option.value = label;
            option.textContent = label;
            select.appendChild(option);
        });
        select.value = labels.includes(selected) ? selected : "";
    }

    function renderKpis(data) {
        const kpi = data.kpi || {};
        document.getElementById("survey-total-observasi").textContent = number(kpi.total_observasi);
        const sales = document.getElementById("survey-total-penjualan");
        sales.textContent = rupiah(kpi.total_penjualan);
        sales.title = "T = triliun, M = miliar, jt = juta";
        document.getElementById("survey-median-margin").textContent = percent(kpi.median_margin * 100);
        document.getElementById("survey-total-tenaga-kerja").textContent = number(kpi.total_tenaga_kerja);
        const rate = kpi.total_observasi ? kpi.usaha_tercluster / kpi.total_observasi * 100 : 0;
        document.getElementById("survey-clustered-rate").textContent = percent(rate);

        const source = data.source || {};
        document.getElementById("survey-source-label").textContent =
            `${source.label || `Survei ${source.year}`} · hasil dibaca dari database, tanpa menghitung ulang model`;
        document.getElementById("survey-source-file").textContent = source.file || "—";
        document.getElementById("survey-source-rows").textContent = number(source.rows);
        document.getElementById("survey-incomplete-count").textContent = number(kpi.data_tidak_lengkap);
        document.getElementById("survey-analysis-version").textContent = data.model?.version || "—";

        const model = data.model || {};
        document.getElementById("survey-model-info").textContent =
            `${model.name || "Model survei"} · eps ${model.eps ?? "-"} · min_samples ${model.min_samples ?? "-"} · ` +
            `${model.n_clusters || 0} cluster · silhouette ${model.silhouette == null ? "-" : Number(model.silhouette).toFixed(4)} · ` +
            `noise ${model.noise_percent || 0}%`;
        const status = document.getElementById("survey-analysis-status");
        if (status) status.textContent = "ready";
    }

    function renderDistribution(chart) {
        const container = document.getElementById("survey-cluster-chart");
        if (!container) return;
        const labels = chart?.labels || [];
        const values = chart?.values || [];
        if (!labels.length) {
            container.innerHTML = '<p class="text-muted text-center py-5 mb-0">Tidak ada data pada filter ini.</p>';
            return;
        }
        const max = Math.max(...values, 1);
        container.innerHTML = labels.map((label, index) => {
            const value = Number(values[index] || 0);
            const width = Math.max(value / max * 100, value ? 4 : 0);
            const noiseClass = label === "Noise" ? " survey-distribution-noise" : "";
            return `<div class="survey-distribution-row">
                <div class="d-flex justify-content-between small mb-1"><span class="fw-semibold">${escape(label)}</span><span class="text-muted">${number(value)} pelaku</span></div>
                <div class="survey-distribution-track"><span class="survey-distribution-fill${noiseClass}" style="width:${width}%"></span></div>
            </div>`;
        }).join("");
    }

    function renderProfiles(profiles) {
        const container = document.getElementById("survey-cluster-profiles");
        if (!container) return;
        container.innerHTML = profiles?.length ? profiles.map(profile => `
            <div class="col-12 col-md-6 col-xl-4">
                <div class="survey-profile-card h-100">
                    <div class="d-flex align-items-center gap-2 mb-2">
                        <span class="survey-profile-dot"></span>
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
            </div>`).join("") : '<div class="col-12 text-muted">Tidak ada profil pada filter ini.</div>';
    }

    function renderActors(data) {
        const body = document.getElementById("survey-actor-table-body");
        const counter = document.getElementById("survey-actor-count");
        const actors = data.items || [];
        const start = (Number(data.page || 1) - 1) * Number(data.per_page || 50);
        if (counter) counter.textContent = `${number(data.total)} pelaku`;
        if (!body) return;
        body.innerHTML = actors.length ? actors.map((actor, index) => {
            const clusterClass = actor.cluster === "Noise"
                ? "bg-warning text-dark"
                : actor.cluster === "Tidak terpetakan" ? "bg-secondary" : "bg-primary";
            const statusClass = actor.status === "Terpetakan" ? "text-success" : "text-muted";
            return `
                <tr>
                    <td>${start + index + 1}</td>
                    <td><strong>${escape(actor.nama_usaha || "—")}</strong><div class="small text-muted">Baris survei ${number(actor.row_number)}</div></td>
                    <td>${escape(actor.subsektor || "—")}</td>
                    <td>${escape(actor.kelurahan || "—")}, ${escape(actor.kecamatan || "—")}</td>
                    <td>${escape(actor.klasifikasi_umkm || "—")}</td>
                    <td><span class="badge ${clusterClass}">${escape(actor.cluster || "—")}</span></td>
                    <td class="${statusClass}">${escape(actor.status || "—")}</td>
                </tr>`;
        }).join("") : '<tr><td colspan="7" class="text-center text-muted py-4">Tidak ada pelaku sesuai filter.</td></tr>';

        const info = document.getElementById("survey-actor-page-info");
        if (info) info.textContent = data.pages
            ? `Halaman ${data.page} dari ${data.pages} · maksimal ${data.per_page} baris per request`
            : "Tidak ada baris";
        document.getElementById("btn-actors-prev")?.toggleAttribute("disabled", !data.pages || data.page <= 1);
        document.getElementById("btn-actors-next")?.toggleAttribute("disabled", !data.pages || data.page >= data.pages);
    }

    function showError(message) {
        const box = document.getElementById("survey-error");
        if (!box) return;
        box.textContent = `Data survei belum dapat dimuat: ${message}`;
        box.classList.remove("d-none");
    }

    async function refresh({ resetPage = false } = {}) {
        if (!year()) return;
        if (resetPage) page = 1;
        const requestId = ++requestNumber;
        const cluster = document.getElementById("survey-filter-cluster")?.value || "";
        const query = new URLSearchParams({ cluster });
        query.set("page", String(page));
        query.set("per_page", "50");
        const summaryUrl = `/api/survey/periods/${encodeURIComponent(year())}/summary?cluster=${encodeURIComponent(cluster)}`;
        const actorsUrl = `/api/survey/periods/${encodeURIComponent(year())}/actors?${query.toString()}`;
        const errorBox = document.getElementById("survey-error");
        errorBox?.classList.add("d-none");
        setLoading(true);
        try {
            const [summary, actors] = await Promise.all([getJson(summaryUrl), getJson(actorsUrl)]);
            if (requestId !== requestNumber) return;
            const labels = summary.charts?.cluster?.labels || [];
            if (!knownClusters.length) {
                knownClusters = labels.slice();
                renderClusterOptions(knownClusters);
            }
            renderKpis(summary);
            renderDistribution(summary.charts?.cluster);
            renderProfiles(summary.profiles);
            renderActors(actors);
            pages = Number(actors.pages || 0);
        } catch (error) {
            if (requestId === requestNumber) showError(error.message);
        } finally {
            if (requestId === requestNumber) setLoading(false);
        }
    }

    function init() {
        if (!root()) return;
        document.getElementById("survey-filter-cluster")?.addEventListener("change", () => refresh({ resetPage: true }));
        document.getElementById("btn-refresh-data")?.addEventListener("click", () => refresh());
        document.getElementById("btn-actors-prev")?.addEventListener("click", () => {
            if (page > 1) { page -= 1; refresh(); }
        });
        document.getElementById("btn-actors-next")?.addEventListener("click", () => {
            if (pages && page < pages) { page += 1; refresh(); }
        });
        refresh();
    }

    return { init, refresh };
})();

document.addEventListener("DOMContentLoaded", () => SurveyPage.init());
