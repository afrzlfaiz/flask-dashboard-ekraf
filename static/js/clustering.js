/**
 * clustering.js — DBSCAN page: run algorithm, display results on map.
 */
let DBScanMap = null;
let dbscanClusterLayer = null;

const CLUSTER_COLORS = ["#dc2626", "#2563eb", "#16a34a", "#ca8a04", "#9333ea", "#0d9488", "#ea580c", "#db2777", "#0891b2", "#4f46e5"];

function initDBScanMap() {
    DBScanMap = L.map("dbscan-map").setView([-7.978, 112.630], 12.5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; OpenStreetMap contributors',
    }).addTo(DBScanMap);
    dbscanClusterLayer = L.layerGroup().addTo(DBScanMap);
}

async function runDBSCAN() {
    const eps = parseFloat(document.getElementById("dbscan-eps").value);
    const minSamples = parseInt(document.getElementById("dbscan-min-samples").value);

    try {
        const body = { ...App.getFilterParams(), eps, min_samples: minSamples };
        const resp = await fetch("/api/dbscan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const result = await resp.json();

        // Update summary
        document.getElementById("dbscan-total-clusters").textContent = result.n_clusters;
        document.getElementById("dbscan-clustered-count").textContent = result.n_clustered;
        document.getElementById("dbscan-noise-count").textContent = result.n_noise;

        // Update map
        dbscanClusterLayer.clearLayers();
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
                    <h6 class="mb-1 fw-bold">${pt.nama_narasumber}</h6>
                    <small class="text-muted d-block">${pt.alamat}</small>
                    <hr class="my-1">
                    <small>Subsektor: <strong>${pt.subsektor}</strong></small>
                    <a href="https://www.google.com/maps?q=${pt.latitude},${pt.longitude}" target="_blank" class="btn btn-sm btn-outline-primary mt-1 w-100" style="font-size: 0.75rem;">
                        <i class="bi bi-geo-alt"></i> Buka di Google Maps
                    </a>
                </div>`);
            dbscanClusterLayer.addLayer(marker);
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
                                <span class="fw-semibold">${cd.dominant_kecamatan.name}</span>
                                <span class="text-muted">(${cd.dominant_kecamatan.count} pelaku, ${cd.dominant_kecamatan.percentage}%)</span>
                            </div>
                            <div class="mb-2">
                                <span class="text-muted"><i class="bi bi-building me-1" style="color:${col};"></i>Kelurahan Dominan:</span>
                                <span class="fw-semibold">${cd.dominant_kelurahan.name}</span>
                                <span class="text-muted">(${cd.dominant_kelurahan.count} pelaku, ${cd.dominant_kelurahan.percentage}%)</span>
                            </div>
                            <div class="mb-2">
                                <span class="text-muted"><i class="bi bi-tag-fill me-1" style="color:${col};"></i>Subsektor Dominan:</span>
                                <span class="fw-semibold">${cd.dominant_subsektor.name}</span>
                                <span class="text-muted">(${cd.dominant_subsektor.count} pelaku, ${cd.dominant_subsektor.percentage}%)</span>
                            </div>
                            <div>
                                <span class="text-muted"><i class="bi bi-crosshair me-1" style="color:${col};"></i>Centroid:</span>
                                <a href="${googleMapsUrl}" target="_blank" class="text-decoration-none">
                                    ${cd.centroid.lat}, ${cd.centroid.lon} <i class="bi bi-box-arrow-up-right" style="font-size:0.65rem;"></i>
                                </a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>`;
    });
}

async function findOptimalDBSCAN() {
    const btn = document.getElementById("btn-optimal-dbscan");
    const hint = document.getElementById("dbscan-optimal-hint");
    const icon = btn.querySelector("i");

    btn.disabled = true;
    icon.className = "bi bi-hourglass-split spin";
    hint.textContent = "Mencari parameter optimal...";

    try {
        const body = { ...App.getFilterParams() };
        const resp = await fetch("/api/dbscan/optimal", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const result = await resp.json();

        if (result.best_score <= 0) {
            hint.textContent = "Tidak ditemukan klaster dengan noise ≤ 50%. Coba longgarkan filter data.";
        } else {
            document.getElementById("dbscan-eps").value = result.best_eps;
            document.getElementById("dbscan-min-samples").value = result.best_min_samples;
            // find noise ratio from the best result
            const bestResult = result.results.find(r => r.eps === result.best_eps && r.min_samples === result.best_min_samples);
            const noisePct = bestResult ? Math.round(bestResult.noise_ratio * 100) : "?";
            hint.textContent = `Optimal: eps=${result.best_eps}, min_samples=${result.best_min_samples} | silhouette=${result.best_score}, ${result.best_n_clusters} klaster, noise ${noisePct}%`;
        }

        // auto-run with optimal params
        await runDBSCAN();
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
});
