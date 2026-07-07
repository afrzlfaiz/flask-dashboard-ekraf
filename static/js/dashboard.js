/**
 * dashboard.js — Overview page: Leaflet map, KPI, Plotly charts, density heatmap.
 */
let MainMap = null;
let DensityMap = null;
let markerClusterGroup = null;
let densityHeatLayer = null;

// ── Subsektor color palette ──────────────────────────
const SUBSECTOR_COLORS = {
    "1) Arsitektur": "#1f77b4",
    "2) Seni Rupa": "#ff7f0e",
    "3) Desain Produk": "#2ca02c",
    "4) Film, Animasi, & Video": "#d62728",
    "5) Fotografi": "#9467bd",
    "6) Musik": "#8c564b",
    "7) Desain Interior": "#e377c2",
    "8) Kuliner": "#7f7f7f",
    "9) Fesyen": "#bcbd22",
    "10) DKV": "#17becf",
    "11) Televisi & Radio": "#aec7e8",
    "12) Kriya": "#ffbb78",
    "13) Seni Pertunjukan": "#98df8a",
    "14) Penerbitan": "#ff9896",
    "15) Aplikasi": "#c5b0d5",
    "16) Game Developer": "#c49c94",
    "17) Periklanan": "#f7b6d2",
};

function getSubsektorColor(sub) {
    return SUBSECTOR_COLORS[sub] || "#64748b";
}

// ── Map initialization ───────────────────────────────
function initMaps() {
    // Main Persebaran Map
    MainMap = L.map("main-map").setView([-7.978, 112.630], 12.5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; OpenStreetMap contributors',
    }).addTo(MainMap);
    markerClusterGroup = L.markerClusterGroup();
    MainMap.addLayer(markerClusterGroup);

    // Density Heatmap Map
    DensityMap = L.map("density-map").setView([-7.978, 112.630], 12.5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; OpenStreetMap contributors',
    }).addTo(DensityMap);

    const heatLegend = L.control({ position: "bottomright" });
    heatLegend.onAdd = function () {
        const div = L.DomUtil.create("div", "heatmap-overlay-legend");
        div.innerHTML = `
            <strong style="color: #1e3a8a;">Tingkat Kepadatan</strong><br>
            <div style="height: 10px; background: linear-gradient(to right, blue, lime, yellow, red); border-radius: 4px; margin: 4px 0;"></div>
            <div class="d-flex justify-content-between" style="font-size: 9px; color: #64748b;">
                <span>Rendah</span><span>Tinggi</span>
            </div>`;
        return div;
    };
    heatLegend.addTo(DensityMap);
}

// ── Render main map markers ──────────────────────────
async function updateMainMap() {
    if (!markerClusterGroup || !MainMap) return;
    markerClusterGroup.clearLayers();

    try {
        const q = App.buildFilterQuery();
        const resp = await fetch(`/api/map?${q}`);
        const data = await resp.json();

        data.markers.forEach(m => {
            const color = getSubsektorColor(m.subsektor);
            const icon = L.divIcon({
                html: `<div style="background-color: ${color}; width: 14px; height: 14px; border: 2px solid white; border-radius: 50%; box-shadow: 0 0 5px rgba(0,0,0,0.3)"></div>`,
                className: "custom-map-pin",
                iconSize: [14, 14],
            });
            const marker = L.marker([m.latitude, m.longitude], { icon });
            marker.bindPopup(`
                <div style="font-family: 'Inter', sans-serif; min-width: 180px;">
                    <span class="badge mb-1" style="background-color: ${color}">${m.subsektor}</span>
                    <h6 class="fw-bold mb-0 text-primary">${m.nama_narasumber}</h6>
                    <small class="text-muted d-block mb-1">${m.alamat}</small>
                    <hr class="my-1">
                    <p class="mb-1 small"><strong>Kec:</strong> ${m.kecamatan} | <strong>Kel:</strong> ${m.kelurahan}</p>
                    <a href="https://www.google.com/maps?q=${m.latitude},${m.longitude}" target="_blank" class="btn btn-sm btn-outline-primary mt-1 w-100" style="font-size: 0.75rem;">
                        <i class="bi bi-geo-alt"></i> Buka di Google Maps
                    </a>
                </div>`);
            markerClusterGroup.addLayer(marker);
        });

        // Add GeoJSON boundaries
        if (data.boundaries?.kota) {
            L.geoJSON(data.boundaries.kota, {
                style: { color: "#003f87", fillColor: "#003f87", fillOpacity: 0.02, weight: 1.5, dashArray: "4, 4" },
            }).addTo(MainMap);
        }
        if (data.boundaries?.kecamatan) {
            Object.values(data.boundaries.kecamatan).forEach(geojson => {
                L.geoJSON(geojson, {
                    style: { color: "#115cb9", fillColor: "#115cb9", fillOpacity: 0.04, weight: 1 },
                }).addTo(MainMap);
            });
        }
    } catch (err) {
        console.error("Map load error:", err);
    }
}

// ── Density heatmap ──────────────────────────────────
async function updateDensityHeatmap() {
    if (!DensityMap) return;
    try {
        const container = document.getElementById("density-map");
        if (!container || container.offsetWidth === 0) return;

        // Remove existing heat layer
        DensityMap.eachLayer(layer => {
            if (layer._latlngs || layer.setLatLngs) DensityMap.removeLayer(layer);
        });

        const q = App.buildFilterQuery();
        const resp = await fetch(`/api/map?${q}`);
        const data = await resp.json();
        if (!data.markers.length) return;

        const heatPoints = data.markers.map(m => [m.latitude, m.longitude, 0.5]);
        L.heatLayer(heatPoints, {
            radius: 25, blur: 15, maxZoom: 15,
            gradient: { 0.4: "blue", 0.6: "lime", 0.8: "yellow", 1.0: "red" },
        }).addTo(DensityMap);

        // Add GeoJSON boundary overlays to density map
        if (data.boundaries?.kota) {
            L.geoJSON(data.boundaries.kota, {
                style: { color: "#003f87", fillColor: "#003f87", fillOpacity: 0.02, weight: 1.5, dashArray: "4, 4" },
            }).addTo(DensityMap);
        }
        if (data.boundaries?.kecamatan) {
            Object.values(data.boundaries.kecamatan).forEach(geojson => {
                L.geoJSON(geojson, {
                    style: { color: "#115cb9", fillColor: "#115cb9", fillOpacity: 0.04, weight: 1 },
                }).addTo(DensityMap);
            });
        }
    } catch (err) {
        console.error("Heatmap error:", err);
    }
}

// ── Plotly Charts ────────────────────────────────────
async function renderCharts() {
    const q = App.buildFilterQuery();

    // Donut: Kecamatan distribution
    try {
        const resp = await fetch(`/api/chart/kecamatan?${q}`);
        const d = await resp.json();
        Plotly.newPlot("kecamatan-donut-chart", [{
            values: d.values, labels: d.labels, type: "pie", hole: 0.6,
            marker: { colors: ["#003f87", "#115cb9", "#3b82f6", "#60a5fa", "#93c5fd", "#cbd5e1"] },
            textinfo: "percent", hoverinfo: "label+value", textposition: "inside",
        }], {
            margin: { l: 10, r: 10, t: 10, b: 10 },
            showlegend: true, legend: { orientation: "h", x: 0, y: -0.1, font: { size: 10 } },
            height: 230,
        }, { responsive: true, displayModeBar: false });
    } catch (e) { console.error("Donut chart:", e); }

    // Bar: Subsektor
    try {
        const resp = await fetch(`/api/chart/subsektor?${q}`);
        const d = await resp.json();
        Plotly.newPlot("subsektor-bar-chart", [{
            x: d.labels, y: d.values, type: "bar",
            marker: { color: "#003f87", borderRadius: 8 },
            text: d.values.map(v => v.toLocaleString("id-ID")),
            textposition: "outside",
            textfont: { size: 10, color: "#1e293b" },
        }], {
            margin: { l: 30, r: 10, t: 30, b: 80 },
            font: { family: "Inter", size: 10 }, xaxis: { tickangle: 45 },
            yaxis: { gridcolor: "#f1f5f9" },
            plot_bgcolor: "rgba(0,0,0,0)", paper_bgcolor: "rgba(0,0,0,0)", height: 300,
        }, { responsive: true, displayModeBar: false });
    } catch (e) { console.error("Bar chart:", e); }

    // Top 10 Kelurahan
    try {
        const resp = await fetch(`/api/chart/kelurahan?${q}`);
        const d = await resp.json();
        const container = document.getElementById("top-kelurahan-list");
        container.innerHTML = "";
        if (!d.labels.length) {
            container.innerHTML = '<p class="text-muted text-center py-2 small">Tidak ada data</p>';
        } else {
            const total = d.values.reduce((a, b) => a + b, 0);
            d.labels.forEach((name, i) => {
                const val = d.values[i];
                const pct = Math.round((val / total) * 100) || 0;
                container.innerHTML += `
                    <div class="mb-2">
                        <div class="d-flex justify-content-between text-muted mb-1" style="font-size: 0.75rem;">
                            <span class="fw-semibold text-dark">${name}</span>
                            <span>${val} (${pct}%)</span>
                        </div>
                        <div class="progress" style="height: 5px;">
                            <div class="progress-bar bg-primary" role="progressbar" style="width: ${pct}%"></div>
                        </div>
                    </div>`;
            });
        }
    } catch (e) { console.error("Kelurahan list:", e); }

    // Latest 5 data
    try {
        const resp = await fetch(`/api/table?${q}`);
        const d = await resp.json();
        const tbody = document.getElementById("overview-latest-table-body");
        tbody.innerHTML = "";
        const latest = d.data.slice(-5).reverse();
        if (!latest.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">Tidak ada data sesuai filter</td></tr>';
        } else {
            latest.forEach(item => {
                tbody.innerHTML += `
                    <tr>
                        <td><strong class="text-dark">${item.nama_narasumber}</strong></td>
                        <td><span class="badge bg-primary">${item.subsektor}</span></td>
                        <td>${item.kecamatan}</td>
                        <td>${item.kelurahan}</td>
                    </tr>`;
            });
        }
    } catch (e) { console.error("Latest table:", e); }
}

// ── Called by App.applyFilters() ─────────────────────
async function refreshOverview() {
    await Promise.all([updateMainMap(), updateDensityHeatmap(), renderCharts()]);
}

// ── Init on DOM ready ────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initMaps();
    // Invalidate on tab visibility change
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            if (MainMap) MainMap.invalidateSize();
            if (DensityMap) DensityMap.invalidateSize();
        }
    });
});
