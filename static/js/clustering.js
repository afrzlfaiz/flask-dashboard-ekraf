/**
 * clustering.js — DBSCAN page: run algorithm, display results on map.
 */
let DBScanMap = null;
let dbscanClusterLayer = null;
let dbscanBoundaryLayer = null;

const CLUSTER_COLORS = ["#dc2626", "#2563eb", "#16a34a", "#ca8a04", "#9333ea", "#0d9488", "#ea580c", "#db2777", "#0891b2", "#4f46e5"];

function initDBScanMap() {
    const container = document.getElementById("dbscan-map");
    if (!container || typeof L === "undefined") return null;

    if (!DBScanMap) {
        DBScanMap = L.map(container, { preferCanvas: true }).setView([-7.978, 112.630], 12.5);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; OpenStreetMap contributors',
        }).addTo(DBScanMap);
        dbscanBoundaryLayer = L.layerGroup().addTo(DBScanMap);
        // ponytail: boundaries statis — di-fetch sekali lewat loadBoundaries() dari dashboard.js.
        if (typeof loadBoundaries === "function") {
            loadBoundaries().then(bounds => {
                if (bounds?.kota) {
                    L.geoJSON(bounds.kota, {
                        style: { color: "#003f87", fillColor: "#003f87", fillOpacity: 0.02, weight: 1.5, dashArray: "4, 4" },
                    }).addTo(dbscanBoundaryLayer);
                }
                if (bounds?.kecamatan) {
                    Object.values(bounds.kecamatan).forEach(geojson => {
                        L.geoJSON(geojson, {
                            style: { color: "#115cb9", fillColor: "#115cb9", fillOpacity: 0.04, weight: 1 },
                        }).addTo(dbscanBoundaryLayer);
                    });
                }
            });
        }
    }
    if (!dbscanClusterLayer) {
        dbscanClusterLayer = L.layerGroup().addTo(DBScanMap);
    }
    return dbscanClusterLayer;
}

async function runDBSCAN() {
    const epsMeters = parseFloat(document.getElementById("dbscan-eps").value);
    const minSamples = parseInt(document.getElementById("dbscan-min-samples").value);

    try {
        const clusterLayer = initDBScanMap();
        if (!clusterLayer) throw new Error("Peta klaster belum siap. Muat ulang halaman dan coba kembali.");
        if (!Number.isFinite(epsMeters) || !Number.isInteger(minSamples)) {
            throw new Error("Parameter Epsilon dan Min Samples tidak valid.");
        }

        const body = { ...App.getFilterParams(), eps: epsMeters, min_samples: minSamples };
        const resp = await fetch("/api/dbscan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const result = await resp.json();
        if (!resp.ok) throw new Error(result.error || result.message || `Server merespons ${resp.status}.`);
        if (!Array.isArray(result.points) || !Array.isArray(result.cluster_details)) {
            throw new Error("Format hasil DBSCAN tidak valid.");
        }

        // Update summary
        document.getElementById("dbscan-total-clusters").textContent = result.n_clusters;
        document.getElementById("dbscan-clustered-count").textContent = result.n_clustered;
        document.getElementById("dbscan-noise-count").textContent = result.n_noise;

        // Update map
        clusterLayer.clearLayers();
        result.points.forEach(pt => {
            const color = pt.is_noise ? "#94a3b8" : CLUSTER_COLORS[(pt.cluster % CLUSTER_COLORS.length)];
            const label = pt.is_noise ? "Noise" : `Klaster #${pt.cluster + 1}`;
            const icon = L.divIcon({
                html: `<div style="background-color: ${color}; width: 14px; height: 14px; border: 2px solid white; border-radius: 50%; box-shadow: 0 0 5px rgba(0,0,0,0.4)"></div>`,
                className: "cluster-map-pin",
                iconSize: [14, 14],
            });
            const marker = L.marker([pt.latitude, pt.longitude], { icon });
            marker.bindPopup(`
                <div style="font-family:'Inter', sans-serif;">
                    <span class="badge ${pt.is_noise ? 'bg-danger' : 'bg-primary'} mb-1">${label}</span>
                    <h6 class="mb-1 fw-bold">${App.escapeHTML(pt.nama_narasumber)}</h6>
                    <small class="text-muted d-block">${App.escapeHTML(pt.alamat)}</small>
                    <hr class="my-1">
                    <small>Subsektor: <strong>${App.escapeHTML(pt.subsektor)}</strong></small>
                    <a href="https://www.google.com/maps?q=${pt.latitude},${pt.longitude}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary mt-1 w-100" style="font-size: 0.75rem;">
                        <i class="bi bi-geo-alt"></i> Buka di Google Maps
                    </a>
                </div>`);
            clusterLayer.addLayer(marker);
        });

        // Update cluster details
        const detailContainer = document.getElementById("dbscan-cluster-details");
        detailContainer.innerHTML = "";
        if (result.n_clusters === 0) {
            detailContainer.innerHTML = '<p class="text-danger text-center small my-3">Tidak ada klaster terbentuk. Kurangi Epsilon atau kurangi Min Samples.</p>';
        } else {
            result.cluster_details.forEach(cd => {
                const col = CLUSTER_COLORS[(cd.cluster_id % CLUSTER_COLORS.length)];
                detailContainer.innerHTML += `
                    <div class="d-flex justify-content-between align-items-center mb-2 p-2 border-bottom">
                        <div class="d-flex align-items-center gap-2">
                            <span class="d-inline-block" style="width: 12px; height: 12px; border-radius: 50%; background-color: ${col}"></span>
                            <span class="fw-bold small">Klaster #${cd.cluster_id + 1}</span>
                        </div>
                        <span class="badge bg-secondary rounded-pill">${cd.size} Pelaku (${cd.percentage}%)</span>
                    </div>`;
            });
        }

        // Render cluster characteristic profiles
        renderClusterProfiles(result);

        App.showToast("DBSCAN", `${result.n_clusters} klaster terbentuk, ${result.n_noise} noise.`);
    } catch (err) {
        App.showToast("Error", "Gagal menjalankan DBSCAN: " + err.message);
    }
}

function renderClusterProfiles(result) {
    const card = document.getElementById("dbscan-cluster-profile-card");
    const container = document.getElementById("dbscan-cluster-profiles");

    if (!result.cluster_details || result.cluster_details.length === 0) {
        card.style.display = "none";
        return;
    }

    card.style.display = "block";
    container.innerHTML = "";

    result.cluster_details.forEach(cd => {
        const col = CLUSTER_COLORS[(cd.cluster_id % CLUSTER_COLORS.length)];
        const googleMapsUrl = `https://www.google.com/maps?q=${cd.centroid.lat},${cd.centroid.lon}`;

        container.innerHTML += `
            <div class="col-12 col-md-6 col-xl-4">
                <div class="card border-0 shadow-sm h-100" style="border-left: 4px solid ${col};">
                    <div class="card-body p-3">
                        <div class="d-flex align-items-center gap-2 mb-2">
                            <span class="d-inline-block rounded-circle" style="width: 14px; height: 14px; background-color: ${col};"></span>
                            <span class="fw-bold">Klaster #${cd.cluster_id + 1}</span>
                            <span class="badge bg-secondary rounded-pill ms-auto">${cd.size} anggota (${cd.percentage}%)</span>
                        </div>
                        <hr class="my-2">
                        <div class="small">
                            <div class="mb-2">
                                <span class="text-muted"><i class="bi bi-geo-alt-fill me-1" style="color:${col};"></i>Kecamatan Dominan:</span>
                                <span class="fw-semibold">${App.escapeHTML(cd.dominant_kecamatan.name)}</span>
                                <span class="text-muted">(${cd.dominant_kecamatan.count} pelaku, ${cd.dominant_kecamatan.percentage}%)</span>
                            </div>
                            <div class="mb-2">
                                <span class="text-muted"><i class="bi bi-building me-1" style="color:${col};"></i>Kelurahan Dominan:</span>
                                <span class="fw-semibold">${App.escapeHTML(cd.dominant_kelurahan.name)}</span>
                                <span class="text-muted">(${cd.dominant_kelurahan.count} pelaku, ${cd.dominant_kelurahan.percentage}%)</span>
                            </div>
                            <div class="mb-2">
                                <span class="text-muted"><i class="bi bi-tag-fill me-1" style="color:${col};"></i>Subsektor Dominan:</span>
                                <span class="fw-semibold">${App.escapeHTML(cd.dominant_subsektor.name)}</span>
                                <span class="text-muted">(${cd.dominant_subsektor.count} pelaku, ${cd.dominant_subsektor.percentage}%)</span>
                            </div>
                            <div>
                                <span class="text-muted"><i class="bi bi-crosshair me-1" style="color:${col};"></i>Centroid:</span>
                                <a href="${googleMapsUrl}" target="_blank" rel="noopener noreferrer" class="text-decoration-none">
                                    ${cd.centroid.lat}, ${cd.centroid.lon} <i class="bi bi-box-arrow-up-right" style="font-size:0.65rem;"></i>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
    });
}

function clearOptimalDBSCANResults() {
    const results = document.getElementById("dbscan-optimal-results");
    const tableBody = document.getElementById("dbscan-optimal-table-body");
    const hint = document.getElementById("dbscan-optimal-hint");
    results?.classList.add("d-none");
    if (tableBody) tableBody.innerHTML = "";
    if (hint) hint.textContent = "";
}

function renderOptimalDBSCANResults(result) {
    const results = document.getElementById("dbscan-optimal-results");
    const tableBody = document.getElementById("dbscan-optimal-table-body");
    tableBody.innerHTML = result.candidates.map(candidate => `
        <tr>
            <td><span class="badge ${candidate.rank === 1 ? "bg-warning text-dark" : "bg-secondary"}">#${candidate.rank}</span></td>
            <td>${candidate.eps_meters} m <small class="text-muted">(${candidate.eps_kilometers} km)</small></td>
            <td>${candidate.min_samples}</td>
            <td>${candidate.silhouette.toFixed(4)}</td>
            <td><strong>${candidate.balanced_score.toFixed(4)}</strong></td>
            <td>${candidate.n_clusters}</td>
            <td>${candidate.n_noise} <small class="text-muted">(${candidate.noise_percent.toFixed(1)}%)</small></td>
            <td class="text-end">
                <button class="btn btn-primary btn-sm" type="button"
                        data-use-dbscan-eps-meters="${candidate.eps_meters}"
                        data-use-dbscan-min-samples="${candidate.min_samples}">
                    Gunakan
                </button>
            </td>
        </tr>`).join("");
    results.classList.remove("d-none");
}

async function findOptimalDBSCAN() {
    const btn = document.getElementById("btn-optimal-dbscan");
    const hint = document.getElementById("dbscan-optimal-hint");
    const icon = btn.querySelector("i");

    clearOptimalDBSCANResults();
    btn.disabled = true;
    icon.className = "bi bi-hourglass-split spin";
    hint.textContent = "Mengevaluasi 120 kombinasi parameter...";

    try {
        const body = { ...App.getFilterParams() };
        const filterSignature = JSON.stringify(body);
        const resp = await fetch("/api/dbscan/optimal", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const result = await resp.json();
        if (!resp.ok) throw new Error(result.error || result.message || `Server merespons ${resp.status}.`);
        if (!Array.isArray(result.candidates)) throw new Error("Format kandidat parameter tidak valid.");
        if (filterSignature !== JSON.stringify(App.getFilterParams())) return;

        if (!result.candidates.length) {
            hint.textContent = "Tidak ditemukan kombinasi dengan 2–15 klaster, silhouette positif, dan noise ≤ 50%.";
        } else {
            renderOptimalDBSCANResults(result);
            hint.textContent = `${result.candidates.length} kandidat terbaik dari ${result.combinations_evaluated} kombinasi dan ${result.total_points} titik.`;
        }
    } catch (err) {
        hint.textContent = "Gagal: " + err.message;
    } finally {
        btn.disabled = false;
        icon.className = "bi bi-magic";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // DBSCAN map is lazily initialized when the page is first shown (see app.js switchPage)
    document.getElementById("btn-run-dbscan").addEventListener("click", runDBSCAN);
    document.getElementById("btn-optimal-dbscan").addEventListener("click", findOptimalDBSCAN);
    document.getElementById("dbscan-optimal-table-body").addEventListener("click", async event => {
        const button = event.target.closest("[data-use-dbscan-eps-meters]");
        if (!button) return;
        document.getElementById("dbscan-eps").value = button.dataset.useDbscanEpsMeters;
        document.getElementById("dbscan-min-samples").value = button.dataset.useDbscanMinSamples;
        await runDBSCAN();
    });
});
