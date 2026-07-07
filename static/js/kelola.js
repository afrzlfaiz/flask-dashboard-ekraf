/**
 * kelola.js — CRUD operations: form handling, import Excel, manage list.
 */
const Kelola = {
    // ── Refresh the manage list table ──────────────────
    async refreshList() {
        const q = App.buildFilterQuery();
        try {
            const resp = await fetch(`/api/table?${q}`);
            const result = await resp.json();
            const tbody = document.getElementById("crud-list-table-body");
            tbody.innerHTML = "";
            result.data.forEach(item => {
                tbody.innerHTML += `
                    <tr>
                        <td><strong>${item.nama_narasumber}</strong></td>
                        <td>${item.nama_usaha}</td>
                        <td><span class="badge bg-light text-dark">${item.subsektor}</span></td>
                        <td class="text-end">
                            <button class="btn btn-sm btn-link text-warning p-0 me-2" onclick="Kelola.editActor(${item.id})"><i class="bi bi-pencil-fill"></i></button>
                            <button class="btn btn-sm btn-link text-danger p-0" onclick="Kelola.deleteActor(${item.id})"><i class="bi bi-trash-fill"></i></button>
                        </td>
                    </tr>`;
            });
        } catch (err) {
            console.error("Kelola list error:", err);
        }
    },

    // ── Edit actor — fill form ─────────────────────────
    async editActor(id) {
        App.switchPage("manage-page");
        try {
            const resp = await fetch("/api/crud");
            const result = await resp.json();
            const actor = result.data.find(x => x.id === id);
            if (!actor) return;

            document.getElementById("crud-form-title").innerHTML = '<i class="bi bi-pencil-square me-2 text-warning"></i>Edit Data Pelaku';
            document.getElementById("crud-id").value = actor.id;
            document.getElementById("crud-nama-narasumber").value = actor.nama_narasumber;
            document.getElementById("crud-nama-usaha").value = actor.nama_usaha;
            document.getElementById("crud-kecamatan").value = actor.kecamatan;

            // Trigger kelurahan load
            document.getElementById("crud-kecamatan").dispatchEvent(new Event("change"));
            setTimeout(() => { document.getElementById("crud-kelurahan").value = actor.kelurahan; }, 300);

            document.getElementById("crud-alamat").value = actor.alamat || "";
            document.getElementById("crud-latitude").value = actor.latitude || "";
            document.getElementById("crud-longitude").value = actor.longitude || "";
            document.getElementById("crud-subsektor").value = actor.subsektor || "";
            document.getElementById("crud-kategori").value = actor.kategori_usaha || "";
            document.getElementById("crud-tahun").value = actor.tahun_berdiri || "";
            document.getElementById("crud-hp").value = actor.no_hp || "";
            document.getElementById("crud-email").value = actor.email || "";

            document.getElementById("btn-cancel-crud").style.display = "block";
            document.getElementById("btn-submit-crud").textContent = "Perbarui Pelaku";
            window.scrollTo({ top: 0, behavior: "smooth" });
        } catch (err) {
            App.showToast("Error", "Gagal memuat data: " + err.message);
        }
    },

    // ── Delete actor ───────────────────────────────────
    async deleteActor(id) {
        if (!confirm("Hapus data pelaku ekonomi kreatif ini?")) return;
        try {
            const resp = await fetch(`/api/crud/${id}`, { method: "DELETE" });
            if (resp.ok) {
                App.showToast("Dihapus", "Data berhasil dihapus.");
                await App.applyFilters();
            }
        } catch (err) {
            App.showToast("Error", "Gagal menghapus: " + err.message);
        }
    },

    // ── Reset form to "add" mode ───────────────────────
    resetForm() {
        document.getElementById("actor-crud-form").reset();
        document.getElementById("crud-id").value = "";
        document.getElementById("crud-form-title").innerHTML = '<i class="bi bi-plus-circle-fill me-2"></i>Tambah Data Pelaku';
        document.getElementById("btn-cancel-crud").style.display = "none";
        document.getElementById("btn-submit-crud").textContent = "Simpan Pelaku";
    },

    // ── Handle file import ─────────────────────────────
    async importFile(file) {
        if (!file) return;
        const progressBar = document.getElementById("import-progress-bar");
        const progressInner = progressBar.querySelector(".progress-bar");
        progressBar.classList.remove("d-none");
        progressInner.style.width = "0%";

        // Simulate progress
        let progress = 0;
        const interval = setInterval(() => {
            progress += 20;
            progressInner.style.width = `${Math.min(progress, 90)}%`;
        }, 150);

        try {
            const formData = new FormData();
            formData.append("file", file);
            const resp = await fetch("/api/upload", { method: "POST", body: formData });
            const result = await resp.json();

            clearInterval(interval);
            progressInner.style.width = "100%";
            setTimeout(() => {
                progressBar.classList.add("d-none");
                if (resp.ok) {
                    App.showToast("Import Berhasil", result.message);
                    App.applyFilters();
                } else {
                    App.showToast("Error", result.error);
                }
            }, 500);
        } catch (err) {
            clearInterval(interval);
            progressBar.classList.add("d-none");
            App.showToast("Error", "Gagal import: " + err.message);
        }
    },
};

// ── Global hook for tabel.js ──
window.refreshKelolaList = () => Kelola.refreshList();

// ── Event bindings ────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    // CRUD form submit
    document.getElementById("actor-crud-form").addEventListener("submit", async function (e) {
        e.preventDefault();
        const crudId = document.getElementById("crud-id").value;
        const body = {
            nama_narasumber: document.getElementById("crud-nama-narasumber").value,
            nama_usaha: document.getElementById("crud-nama-usaha").value,
            kecamatan: document.getElementById("crud-kecamatan").value,
            kelurahan: document.getElementById("crud-kelurahan").value,
            alamat: document.getElementById("crud-alamat").value,
            latitude: parseFloat(document.getElementById("crud-latitude").value),
            longitude: parseFloat(document.getElementById("crud-longitude").value),
            subsektor: document.getElementById("crud-subsektor").value,
            kategori_usaha: document.getElementById("crud-kategori").value || "",
            tahun_berdiri: parseInt(document.getElementById("crud-tahun").value) || null,
            no_hp: document.getElementById("crud-hp").value || "",
            email: document.getElementById("crud-email").value || "",
        };

        try {
            let resp;
            if (crudId) {
                resp = await fetch(`/api/crud/${crudId}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });
            } else {
                resp = await fetch("/api/crud", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(body),
                });
            }
            if (resp.ok) {
                Kelola.resetForm();
                await App.applyFilters();
                App.showToast("Sukses", crudId ? "Data berhasil diperbarui." : "Data berhasil ditambahkan.");
            }
        } catch (err) {
            App.showToast("Error", "Gagal menyimpan: " + err.message);
        }
    });

    // Cancel button
    document.getElementById("btn-cancel-crud").addEventListener("click", () => Kelola.resetForm());

    // Drag & drop import
    const dropZone = document.getElementById("excel-drop-zone");
    const fileInput = document.getElementById("excel-file-input");

    ["dragenter", "dragover"].forEach(ev => {
        dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add("bg-secondary-subtle"); });
    });
    ["dragleave", "drop"].forEach(ev => {
        dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove("bg-secondary-subtle"); });
    });
    dropZone.addEventListener("drop", e => Kelola.importFile(e.dataTransfer.files[0]));
    fileInput.addEventListener("change", e => Kelola.importFile(e.target.files[0]));
});
