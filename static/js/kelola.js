/**
 * kelola.js — CRUD operations: form handling, import Excel, manage list.
 */
const Kelola = {
    currentImportBatch: null,

    // ── Refresh the manage list table ──────────────────
    async refreshList() {
        const q = App.buildFilterQuery();
        try {
            if (!Auth.isAuthenticated()) return;
            const includeInactive = Auth.hasRole("admin") ? "?include_inactive=1" : "";
            const resp = await fetch(`/api/crud${includeInactive}`);
            if (!resp.ok) return;
            const result = await resp.json();
            const tbody = document.getElementById("crud-list-table-body");
            tbody.innerHTML = "";
            result.data.forEach(item => {
                    const deleteBtn = Auth.hasRole("admin") && item.is_active
                        ? `<button class="btn btn-sm btn-link text-danger p-0" onclick="Kelola.deleteActor(${item.id})" title="Nonaktifkan"><i class="bi bi-trash-fill"></i></button>`
                        : "";
                    const restoreBtn = Auth.hasRole("admin") && !item.is_active
                        ? `<button class="btn btn-sm btn-link text-success p-0" onclick="Kelola.restoreActor(${item.id})" title="Pulihkan"><i class="bi bi-arrow-counterclockwise"></i></button>`
                        : "";
                    tbody.innerHTML += `
                        <tr>
                            <td><strong>${App.escapeHTML(item.nama_narasumber)}</strong>${item.is_active ? "" : '<span class="badge bg-secondary ms-1">Nonaktif</span>'}</td>
                            <td>${App.escapeHTML(item.nama_usaha)}</td>
                            <td><span class="badge bg-light text-dark">${App.escapeHTML(item.subsektor)}</span></td>
                            <td class="text-end">
                                ${item.is_active ? `<button class="btn btn-sm btn-link text-warning p-0 me-2" onclick="Kelola.editActor(${item.id})"><i class="bi bi-pencil-fill"></i></button>` : ""}
                                ${deleteBtn}
                                ${restoreBtn}
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
        if (!Auth.require("admin")) return;
        if (!confirm("Nonaktifkan data pelaku ekonomi kreatif ini?")) return;
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

    async restoreActor(id) {
        if (!Auth.require("admin")) return;
        try {
            const resp = await fetch(`/api/crud/${id}/restore`, { method: "POST" });
            const result = await resp.json();
            if (!resp.ok) throw new Error(result.message || "Gagal memulihkan data.");
            App.showToast("Dipulihkan", result.message);
            await App.applyFilters();
        } catch (err) {
            App.showToast("Error", err.message);
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
        if (!Auth.require("operator")) return;
        if (!file.name.toLowerCase().endsWith(".xlsx")) {
            App.showToast("File Ditolak", "Hanya file XLSX yang dapat diunggah.");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            App.showToast("File Ditolak", "Ukuran file melebihi 10 MB.");
            return;
        }
        const progressBar = document.getElementById("import-progress-bar");
        const progressInner = progressBar.querySelector(".progress-bar");
        progressBar.classList.remove("d-none");
        progressInner.style.width = "0%";
        progressInner.setAttribute("aria-valuenow", "0");

        // Simulate progress
        let progress = 0;
        const interval = setInterval(() => {
            progress += 20;
            progressInner.style.width = `${Math.min(progress, 90)}%`;
            progressInner.setAttribute("aria-valuenow", String(Math.min(progress, 90)));
        }, 150);

        try {
            const formData = new FormData();
            formData.append("file", file);
            const resp = await fetch("/api/upload", { method: "POST", body: formData });
            const result = await resp.json();

            clearInterval(interval);
            progressInner.style.width = "100%";
            progressInner.setAttribute("aria-valuenow", "100");
            setTimeout(() => {
                progressBar.classList.add("d-none");
                if (resp.ok) {
                    this.renderImportPreview(result);
                    App.showToast("Validasi Selesai", result.message);
                } else {
                    App.showToast("Import Ditolak", result.message || "File gagal divalidasi.");
                }
            }, 500);
        } catch (err) {
            clearInterval(interval);
            progressBar.classList.add("d-none");
            App.showToast("Error", "Gagal import: " + err.message);
        }
    },

    renderImportPreview(result) {
        const batch = result.batch;
        this.currentImportBatch = batch.id;
        document.getElementById("import-preview").classList.remove("d-none");
        document.getElementById("import-preview-filename").textContent = `${batch.filename} · Batch ${batch.id.slice(0, 8)}`;
        document.getElementById("import-summary-badges").innerHTML = `
            <span class="badge bg-success">${batch.valid} valid</span>
            <span class="badge bg-danger">${batch.errors} gagal</span>
            <span class="badge bg-warning text-dark">${batch.duplicates} duplikat</span>`;
        const tbody = document.getElementById("import-preview-body");
        tbody.innerHTML = "";
        result.preview.forEach(row => {
            const badge = {
                valid: '<span class="badge bg-success">Valid</span>',
                error: '<span class="badge bg-danger">Gagal</span>',
                duplicate: '<span class="badge bg-warning text-dark">Duplikat</span>',
            }[row.status] || App.escapeHTML(row.status);
            const detail = row.errors.length ? `<small class="text-danger d-block">${App.escapeHTML(row.errors.join("; "))}</small>` : "";
            tbody.innerHTML += `<tr>
                <td>${row.row}</td>
                <td><strong>${App.escapeHTML(row.nama_usaha || row.nama_narasumber)}</strong><small class="text-muted d-block">${App.escapeHTML(row.subsektor)}</small></td>
                <td>${App.escapeHTML(row.kecamatan)}<small class="text-muted d-block">${App.escapeHTML(row.kelurahan)}</small></td>
                <td>${badge}${detail}</td>
            </tr>`;
        });
        const errorsLink = document.getElementById("btn-download-import-errors");
        errorsLink.href = `/api/upload/${batch.id}/errors`;
        errorsLink.classList.toggle("d-none", batch.errors + batch.duplicates === 0);
        document.getElementById("btn-commit-import").classList.toggle("d-none", batch.status !== "preview");
        document.getElementById("btn-cancel-import").classList.toggle("d-none", batch.status !== "preview");
        document.getElementById("btn-rollback-import").classList.add("d-none");
    },

    async commitImport() {
        if (!this.currentImportBatch || !Auth.require("operator")) return;
        const button = document.getElementById("btn-commit-import");
        button.disabled = true;
        try {
            const resp = await fetch(`/api/upload/${this.currentImportBatch}/commit`, { method: "POST" });
            const result = await resp.json();
            if (!resp.ok) throw new Error(result.message || "Commit import gagal.");
            App.showToast("Import Berhasil", result.message);
            button.classList.add("d-none");
            document.getElementById("btn-cancel-import").classList.add("d-none");
            document.getElementById("btn-rollback-import").classList.toggle("d-none", !Auth.hasRole("admin"));
            await App.applyFilters();
        } catch (err) {
            App.showToast("Error", err.message);
        } finally {
            button.disabled = false;
        }
    },

    async cancelImport() {
        if (!this.currentImportBatch || !Auth.require("operator")) return;
        try {
            const resp = await fetch(`/api/upload/${this.currentImportBatch}/cancel`, { method: "POST" });
            const result = await resp.json();
            if (!resp.ok) throw new Error(result.message || "Pembatalan gagal.");
            document.getElementById("import-preview").classList.add("d-none");
            this.currentImportBatch = null;
            App.showToast("Dibatalkan", result.message);
        } catch (err) {
            App.showToast("Error", err.message);
        }
    },

    async rollbackImport() {
        if (!this.currentImportBatch || !Auth.require("admin")) return;
        if (!confirm("Rollback seluruh data dari batch import ini?")) return;
        try {
            const resp = await fetch(`/api/upload/${this.currentImportBatch}/rollback`, { method: "POST" });
            const result = await resp.json();
            if (!resp.ok) throw new Error(result.message || "Rollback gagal.");
            document.getElementById("btn-rollback-import").classList.add("d-none");
            App.showToast("Rollback Selesai", result.message);
            await App.applyFilters();
        } catch (err) {
            App.showToast("Error", err.message);
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
        if (!Auth.require("operator")) return;
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
    const selectFileButton = document.getElementById("btn-select-file");
    document.getElementById("btn-commit-import").addEventListener("click", () => Kelola.commitImport());
    document.getElementById("btn-cancel-import").addEventListener("click", () => Kelola.cancelImport());
    document.getElementById("btn-rollback-import").addEventListener("click", () => Kelola.rollbackImport());

    ["dragenter", "dragover"].forEach(ev => {
        dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add("is-dragging"); });
    });
    ["dragleave", "drop"].forEach(ev => {
        dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove("is-dragging"); });
    });
    dropZone.addEventListener("drop", e => Kelola.importFile(e.dataTransfer.files[0]));
    fileInput.addEventListener("change", e => Kelola.importFile(e.target.files[0]));
    selectFileButton.addEventListener("click", e => {
        e.stopPropagation();
        fileInput.click();
    });
    dropZone.addEventListener("click", e => {
        if (!e.target.closest("button")) fileInput.click();
    });
});
