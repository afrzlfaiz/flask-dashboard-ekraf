"use strict";

(() => {
    const form = document.getElementById("survey-import-form");
    if (!form) return;

    const button = document.getElementById("btn-import-survey");
    const alertBox = document.getElementById("survey-import-alert");
    const showAlert = (type, message) => {
        alertBox.className = `alert alert-${type} mt-3 mb-0 py-2 small`;
        alertBox.textContent = message;
        alertBox.classList.remove("d-none");
    };

    form.addEventListener("submit", async event => {
        event.preventDefault();
        const year = Number.parseInt(document.getElementById("survey-year-input")?.value || "", 10);
        const fileInput = document.getElementById("survey-file-input");
        const file = fileInput?.files?.[0];
        if (!Number.isInteger(year) || year < 2026 || year > 2100) {
            showAlert("danger", "Masukkan tahun survei antara 2026 dan 2100.");
            return;
        }
        if (!file || !file.name.toLowerCase().endsWith(".xlsx")) {
            showAlert("danger", "Pilih file survei dengan format XLSX.");
            return;
        }

        button.disabled = true;
        alertBox.classList.add("d-none");
        try {
            const formData = new FormData(form);
            formData.append("sheet_name", "Sheet6");
            const response = await fetch("/api/survey/import", {
                method: "POST",
                headers: { "X-CSRFToken": document.querySelector('meta[name="csrf-token"]')?.content || "" },
                body: formData,
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || "Import survei gagal.");
            showAlert("success", result.message || "Survei berhasil disimpan.");
            window.location.href = `/survei/periode-${encodeURIComponent(result.period.survey_year)}`;
        } catch (error) {
            showAlert("danger", error.message);
            button.disabled = false;
        }
    });
})();
