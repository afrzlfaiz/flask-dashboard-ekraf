/**
 * tabel.js — DataTables page with server-side data + export.
 */
let dataTableInstance = null;
let tableDependenciesPromise = null;
const tableSortKeys = [
    "id",
    "nama_usaha",
    "subsektor",
    "kecamatan",
    "kelurahan",
    "tahun_berdiri",
    "kontak",
    "id",
];

async function loadTablePage(requestData, callback) {
    const requestedLength = Number(requestData.length);
    const perPage = Math.min(Math.max(requestedLength > 0 ? requestedLength : 10, 1), 100);
    const page = Math.floor(requestData.start / perPage) + 1;
    const order = requestData.order?.[0] || { column: 0, dir: "asc" };
    const params = new URLSearchParams(App.buildFilterQuery());

    params.set("page", String(page));
    params.set("per_page", String(perPage));
    params.set("draw", String(requestData.draw));
    params.set("sort", tableSortKeys[order.column] || "id");
    params.set("direction", order.dir === "desc" ? "desc" : "asc");
    if (requestData.search?.value) params.set("quick_search", requestData.search.value);

    try {
        const response = await fetch(`/api/table?${params}`);
        if (!response.ok) {
            if (response.status === 401) {
                callback({
                    draw: requestData.draw,
                    data: [],
                    recordsTotal: 0,
                    recordsFiltered: 0,
                });
                return;
            }
            throw new Error(`Server merespons ${response.status}`);
        }
        callback(await response.json());
    } catch (error) {
        console.error("Table page error:", error);
        callback({
            draw: requestData.draw,
            data: [],
            recordsTotal: 0,
            recordsFiltered: 0,
        });
        App.showToast("Error", "Gagal memuat halaman tabel.");
    }
}

function initDataTable() {
    dataTableInstance = $("#main-datatable").DataTable({
        responsive: true,
        autoWidth: false,
        processing: true,
        serverSide: true,
        searchDelay: 350,
        pageLength: 10,
        lengthMenu: [10, 25, 50, 100],
        order: [[0, "asc"]],
        ajax: loadTablePage,
        language: {
            search: "Cari Cepat:",
            lengthMenu: "Tampilkan _MENU_ entri",
            info: "Menampilkan _START_ sampai _END_ dari _TOTAL_ pelaku",
            processing: "Memuat data...",
            zeroRecords: "Tidak ada data yang sesuai",
            paginate: { first: "Pertama", last: "Terakhir", next: "Lanjut", previous: "Kembali" },
        },
        columns: [
            { data: "no" },
            {
                data: "nama_usaha",
                render: (value, type) => type === "display" ? App.escapeHTML(value) : value,
            },
            {
                data: "subsektor",
                render: (value, type) => type === "display"
                    ? `<span class="badge bg-outline-primary border border-primary text-primary">${App.escapeHTML(value)}</span>`
                    : value,
            },
            {
                data: "kecamatan",
                render: (value, type) => type === "display" ? App.escapeHTML(value) : value,
            },
            {
                data: "kelurahan",
                render: (value, type) => type === "display" ? App.escapeHTML(value) : value,
            },
            {
                data: "tahun_berdiri",
                render: (value, type) => type === "display" ? App.escapeHTML(value || "-") : value,
            },
            {
                data: null,
                render: (_value, type, row) => {
                    if (type !== "display") return `${row.no_hp || ""} ${row.email || ""}`;
                    return `<small><i class="bi bi-telephone text-success me-1"></i>${App.escapeHTML(row.no_hp || "-")}<br><i class="bi bi-envelope text-info me-1"></i>${App.escapeHTML(row.email || "-")}</small>`;
                },
            },
            {
                data: null,
                orderable: false,
                searchable: false,
                render: (_value, type, row) => {
                    if (type !== "display") return row.id;
                    if (!Auth.isAuthenticated()) return '<small class="text-muted">Login diperlukan</small>';
                    return `<div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-warning" onclick="Kelola.editActor(${row.id})" title="Edit"><i class="bi bi-pencil"></i></button>
                        ${Auth.hasRole("admin") ? `<button class="btn btn-outline-danger" onclick="Kelola.deleteActor(${row.id})" title="Hapus"><i class="bi bi-trash"></i></button>` : ""}
                    </div>`;
                },
            },
        ],
        columnDefs: [
            { responsivePriority: 3, targets: 0 },
            { responsivePriority: 1, targets: 1 },
            { responsivePriority: 2, targets: 2 },
            { responsivePriority: 4, targets: 3 },
            { responsivePriority: 1, targets: 7 },
        ],
    });
}

function ensureTablePage() {
    if (dataTableInstance) return Promise.resolve();
    if (tableDependenciesPromise) return tableDependenciesPromise;

    App.loadStyle("https://cdn.datatables.net/1.13.7/css/dataTables.bootstrap5.min.css");
    App.loadStyle("https://cdn.datatables.net/responsive/2.5.0/css/responsive.bootstrap5.min.css");
    tableDependenciesPromise = App.loadScript("https://code.jquery.com/jquery-3.7.0.min.js")
        .then(() => App.loadScript("https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"))
        .then(() => App.loadScript("https://cdn.datatables.net/1.13.7/js/dataTables.bootstrap5.min.js"))
        .then(() => App.loadScript("https://cdn.datatables.net/responsive/2.5.0/js/dataTables.responsive.min.js"))
        .then(() => App.loadScript("https://cdn.datatables.net/responsive/2.5.0/js/responsive.bootstrap5.min.js"))
        .then(initDataTable);
    return tableDependenciesPromise;
}

function refreshTable() {
    if (!dataTableInstance) return;
    dataTableInstance.ajax.reload(null, true);
}

// Export buttons
document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("btn-export-csv").addEventListener("click", () => {
        window.open(`/api/export?format=csv&${App.buildFilterQuery()}`, "_blank");
    });

    document.getElementById("btn-export-excel").addEventListener("click", () => {
        window.open(`/api/export?format=xlsx&${App.buildFilterQuery()}`, "_blank");
    });
});
