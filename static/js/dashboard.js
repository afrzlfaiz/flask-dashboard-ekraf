/**
 * dashboard.js — Overview page: Leaflet map, KPI, Plotly charts, density heatmap.
 */
let MainMap = null;
let DensityMap = null;
let markerClusterGroup = null;
let densityHeatLayer = null;
let mainBoundaryLayer = null;

// ponytail: boundaries statis — fetch sekali, pakai ulang sepanjang sesi.
let cachedBoundaries = null;
let lastMarkers = null;
let lastMarkerQuery = null;

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
    MainMap = L.map("main-map", { preferCanvas: true }).setView([-7.978, 112.630], 12.5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; OpenStreetMap contributors',
    }).addTo(MainMap);
    markerClusterGroup = L.markerClusterGroup();
    MainMap.addLayer(markerClusterGroup);
    mainBoundaryLayer = L.layerGroup().addTo(MainMap);

    // Density Heatmap Map
    DensityMap = L.map("density-map", { preferCanvas: true }).setView([-7.978, 112.630], 12.5);
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
async function fetchMarkers(q) {
    // ponytail: hindari fetch /api/map ganda — peta & heatmap pakai hasil yang sama.
    if (q === lastMarkerQuery && lastMarkers) return lastMarkers;
    const resp = await fetch(`/api/map?${q}`);
    const data = await resp.json();
    lastMarkerQuery = q;
    lastMarkers = data.markers;
    return data.markers;
}

async function loadBoundaries() {
    if (cachedBoundaries) return cachedBoundaries;
    const resp = await fetch("/api/boundaries");
    cachedBoundaries = await resp.json();
    return cachedBoundaries;
}

async function updateMainMap() {
    if (!markerClusterGroup || !MainMap) return;
    markerClusterGroup.clearLayers();
    mainBoundaryLayer?.clearLayers();

    try {
        const q = App.buildFilterQuery();
        const [markers, boundaries] = await Promise.all([fetchMarkers(q), loadBoundaries()]);

        markers.forEach(m => {
            const color = getSubsektorColor(m.subsektor);
            const markerSize = m.is_aggregate ? Math.min(34, 16 + Math.log2(m.count + 1) * 3) : 14;
            const icon = L.divIcon({
                html: m.is_aggregate
                    ? `<div class="public-map-aggregate" style="background-color:${color};width:${markerSize}px;height:${markerSize}px">${m.count}</div>`
                    : `<div style="background-color: ${color}; width: 14px; height: 14px; border: 2px solid white; border-radius: 50%; box-shadow: 0 0 5px rgba(0,0,0,0.3)"></div>`,
                className: "custom-map-pin",
                iconSize: [markerSize, markerSize],
            });
            const marker = L.marker([m.latitude, m.longitude], { icon });
            marker.bindPopup(m.is_aggregate ? `
                <div style="font-family: 'Inter', sans-serif; min-width: 160px;">
                    <span class="badge bg-primary mb-2">Data publik teragregasi</span>
                    <h6 class="fw-bold mb-1">${m.count} pelaku ekraf</h6>
                    <small class="text-muted">Area grid ±1 km · ${App.escapeHTML(m.kecamatan)}</small>
                    <p class="small mb-0 mt-2">Subsektor dominan: <strong>${App.escapeHTML(m.subsektor)}</strong></p>
                </div>` : `
                <div style="font-family: 'Inter', sans-serif; min-width: 180px;">
                    <span class="badge mb-1" style="background-color: ${color}">${App.escapeHTML(m.subsektor)}</span>
                    <h6 class="fw-bold mb-0 text-primary">${App.escapeHTML(m.nama_narasumber)}</h6>
                    <small class="text-muted d-block mb-1">${App.escapeHTML(m.alamat)}</small>
                    <hr class="my-1">
                    <p class="mb-1 small"><strong>Kec:</strong> ${App.escapeHTML(m.kecamatan)} | <strong>Kel:</strong> ${App.escapeHTML(m.kelurahan)}</p>
                    <a href="https://www.google.com/maps?q=${m.latitude},${m.longitude}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary mt-1 w-100" style="font-size: 0.75rem;">
                        <i class="bi bi-geo-alt"></i> Buka di Google Maps
                    </a>
                </div>`);
            markerClusterGroup.addLayer(marker);
        });

        // Add GeoJSON boundaries
        if (boundaries?.kota) {
            L.geoJSON(boundaries.kota, {
                style: { color: "#003f87", fillColor: "#003f87", fillOpacity: 0.02, weight: 1.5, dashArray: "4, 4" },
            }).addTo(mainBoundaryLayer);
        }
        if (boundaries?.kecamatan) {
            Object.values(boundaries.kecamatan).forEach(geojson => {
                L.geoJSON(geojson, {
                    style: { color: "#115cb9", fillColor: "#115cb9", fillOpacity: 0.04, weight: 1 },
                }).addTo(mainBoundaryLayer);
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

        DensityMap.invalidateSize({ pan: false, animate: false });
        const mapSize = DensityMap.getSize();
        if (!mapSize || mapSize.x <= 0 || mapSize.y <= 0) return;

        // Remove existing heat layer and cancel its pending canvas redraw.
        if (densityHeatLayer && DensityMap.hasLayer(densityHeatLayer)) {
            DensityMap.removeLayer(densityHeatLayer);
            densityHeatLayer = null;
        }
        DensityMap.eachLayer(layer => {
            if (layer._latlngs || layer.setLatLngs) DensityMap.removeLayer(layer);
        });

        const q = App.buildFilterQuery();
        const [markers, boundaries] = await Promise.all([fetchMarkers(q), loadBoundaries()]);
        if (container.offsetWidth === 0 || App.currentPage !== "overview-page") return;
        if (!markers.length) return;

        const heatPoints = markers.map(m => [m.latitude, m.longitude, 0.5]);
        densityHeatLayer = L.heatLayer(heatPoints, {
            radius: 25, blur: 15, maxZoom: 15,
            gradient: { 0.4: "blue", 0.6: "lime", 0.8: "yellow", 1.0: "red" },
        }).addTo(DensityMap);

        // Add GeoJSON boundary overlays to density map
        if (boundaries?.kota) {
            L.geoJSON(boundaries.kota, {
                style: { color: "#003f87", fillColor: "#003f87", fillOpacity: 0.02, weight: 1.5, dashArray: "4, 4" },
            }).addTo(DensityMap);
        }
        if (boundaries?.kecamatan) {
            Object.values(boundaries.kecamatan).forEach(geojson => {
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
    const plotConfig = { responsive: true, displayModeBar: false };

    // Donut: Kecamatan distribution
    try {
        const resp = await fetch(`/api/chart/kecamatan?${q}`);
        const d = await resp.json();
        const donutContainer = document.getElementById("kecamatan-donut-chart");
        if (!donutContainer || donutContainer.offsetWidth === 0 || App.currentPage !== "overview-page") return;
        Plotly.react(donutContainer, [{
            values: d.values, labels: d.labels, type: "pie", hole: 0.6,
            marker: { colors: ["#003f87", "#115cb9", "#3b82f6", "#60a5fa", "#93c5fd", "#cbd5e1"] },
            textinfo: "percent", hoverinfo: "label+value", textposition: "inside",
        }], {
            autosize: true,
            margin: { l: 8, r: 8, t: 8, b: 48 },
            showlegend: true,
            legend: { orientation: "h", x: 0.5, xanchor: "center", y: -0.08, font: { family: "Inter", size: 9 } },
            height: donutContainer.clientHeight || 240,
            paper_bgcolor: "rgba(0,0,0,0)",
        }, plotConfig);
    } catch (e) { console.error("Donut chart:", e); }

    // Bar: Subsektor
    try {
        const resp = await fetch(`/api/chart/subsektor?${q}`);
        const d = await resp.json();
        const barContainer = document.getElementById("subsektor-bar-chart");
        if (!barContainer || barContainer.offsetWidth === 0 || App.currentPage !== "overview-page") return;
        Plotly.react(barContainer, [{
            x: d.values, y: d.labels, type: "bar", orientation: "h",
            marker: { color: "#0b5da8", line: { color: "#064b91", width: 0.5 } },
            text: d.values.map(v => v.toLocaleString("id-ID")),
            textposition: "outside",
            cliponaxis: false,
            hovertemplate: "%{y}<br><b>%{x:,} pelaku</b><extra></extra>",
            textfont: { family: "Inter", size: 9, color: "#334155" },
        }], {
            autosize: true,
            margin: { l: barContainer.clientWidth < 480 ? 118 : 150, r: 34, t: 12, b: 32 },
            font: { family: "Inter", size: 9, color: "#647084" },
            xaxis: { gridcolor: "#edf1f5", zeroline: false, fixedrange: true },
            yaxis: { autorange: "reversed", automargin: true, fixedrange: true },
            plot_bgcolor: "rgba(0,0,0,0)",
            paper_bgcolor: "rgba(0,0,0,0)",
            height: barContainer.clientHeight || 352,
            bargap: 0.28,
        }, plotConfig);
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
                            <span class="fw-semibold text-dark">${App.escapeHTML(name)}</span>
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
        const latestParams = new URLSearchParams(q);
        latestParams.set("page", "1");
        latestParams.set("per_page", "5");
        latestParams.set("sort", "id");
        latestParams.set("direction", "desc");
        const resp = await fetch(`/api/table?${latestParams}`);
        if (resp.status === 401) {
            document.getElementById("overview-latest-table-body").innerHTML =
                '<tr><td colspan="4" class="text-center text-muted py-4">Login untuk melihat data rinci pelaku ekraf.</td></tr>';
            return;
        }
        const d = await resp.json();
        const tbody = document.getElementById("overview-latest-table-body");
        tbody.innerHTML = "";
        const latest = d.data;
        if (!latest.length) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-3">Tidak ada data sesuai filter</td></tr>';
        } else {
            latest.forEach(item => {
                tbody.innerHTML += `
                    <tr>
                        <td><strong class="text-dark">${App.escapeHTML(item.nama_narasumber)}</strong></td>
                        <td><span class="badge bg-primary">${App.escapeHTML(item.subsektor)}</span></td>
                        <td>${App.escapeHTML(item.kecamatan)}</td>
                        <td>${App.escapeHTML(item.kelurahan)}</td>
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
            if (typeof App !== "undefined") App.resizeVisuals();
        }
    });
});
