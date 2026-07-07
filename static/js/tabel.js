/**
 * tabel.js — DataTables page with server-side data + export.
 */
let dataTableInstance = null;

function initDataTable() {
    dataTableInstance = $("#main-datatable").DataTable({
        responsive: true,
        language: {
            search: "Cari Cepat:",
            lengthMenu: "Tampilkan _MENU_ entri",
            info: "Menampilkan _START_ sampai _END_ dari _TOTAL_ pelaku",
            paginate: { first: "Pertama", last: "Terakhir", next: "Lanjut", previous: "Kembali" },
        },
        columns: [
            { data: "no" },
            { data: "nama_usaha" },
            { data: "subsektor" },
            { data: "kecamatan" },
            { data: "kelurahan" },
            { data: "tahun_berdiri" },
            { data: "kontak" },
            { data: "aksi", orderable: false },
        ],
    });
}

async function refreshTable() {
    if (!dataTableInstance) return;
    const q = App.buildFilterQuery();
    try {
        const resp = await fetch(`/api/table?${q}`);
        const result = await resp.json();

        dataTableInstance.clear();
        const rows = result.data.map((item, idx) => ({
            no: idx + 1,
            nama_usaha: item.nama_usaha,
            subsektor: `<span class="badge bg-outline-primary border border-primary text-primary">${item.subsektor}</span>`,
            kecamatan: item.kecamatan,
            kelurahan: item.kelurahan,
            tahun_berdiri: item.tahun_berdiri || "-",
            kontak: `<small><i class="bi bi-telephone text-success me-1"></i>${item.no_hp || "-"}<br><i class="bi bi-envelope text-info me-1"></i>${item.email || "-"}</small>`,
            aksi: `
                <div class="btn-group btn-group-sm">
                    <button class="btn btn-outline-warning" onclick="Kelola.editActor(${item.id})" title="Edit"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-outline-danger" onclick="Kelola.deleteActor(${item.id})" title="Hapus"><i class="bi bi-trash"></i></button>
                </div>`,
        }));
        dataTableInstance.rows.add(rows).draw();
    } catch (err) {
        console.error("Table refresh error:", err);
    }
}

// Export buttons
document.addEventListener("DOMContentLoaded", () => {
    initDataTable();

    document.getElementById("btn-export-csv").addEventListener("click", () => {
        window.open(`/api/export?format=csv&${App.buildFilterQuery()}`, "_blank");
    });

    document.getElementById("btn-export-excel").addEventListener("click", () => {
        window.open(`/api/export?format=xlsx&${App.buildFilterQuery()}`, "_blank");
    });
});
