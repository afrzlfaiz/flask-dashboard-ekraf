# Dashboard Spasial Ekonomi Kreatif Kota Malang

Dashboard web interaktif untuk visualisasi dan analisis spasial persebaran pelaku Ekonomi Kreatif (Ekraf) di Kota Malang. Aplikasi ini dibangun menggunakan **Flask** sebagai backend, **PostgreSQL Supabase** sebagai database, dan visualisasi spasial interaktif menggunakan **Leaflet.js** serta analisis clustering menggunakan algoritma **DBSCAN (scikit-learn)**.

Aplikasi ini dirancang dengan gaya **Modern Government Dashboard** bertema terang (*light theme*), mengutamakan *whitespace*, sudut melengkung (*rounded corners*), bayangan lembut (*soft shadows*), serta tata letak yang responsif.

---

## 🚀 Fitur Utama

1. **Dashboard & KPI Cards**: Ringkasan data penting seperti Total Pelaku Ekraf, Jumlah Kecamatan/Kelurahan, Jumlah Subsektor, dan data valid.
2. **Peta Persebaran Interaktif**: Visualisasi spasial berbasis **Leaflet.js** dengan marker cluster, popup info detail, overlay batas wilayah menggunakan GeoJSON tingkat kecamatan Kota Malang, legenda, dan opsi basemap Google Maps.
3. **Analisis Spasial DBSCAN**: Fitur pengelompokan wilayah (*clustering*) secara *real-time* berdasarkan koordinat geografis (latitude & longitude) menggunakan algoritma DBSCAN dengan parameter dinamis (`eps` dan `min_samples`). Menghasilkan peta klaster dan analisis persentase *noise*.
4. **Statistik & Visualisasi**: Berbagai chart interaktif menggunakan **Plotly.js** untuk menunjukkan distribusi subsektor, kecamatan, kelurahan, dan kategori usaha.
5. **Tabel Data Interaktif**: Pencarian, pengurutan (*sorting*), paginasi data menggunakan **DataTables**, serta fitur ekspor data ke Excel dan CSV.
6. **Kelola Data (CRUD)**: Manajemen data berbasis role, soft-delete/restore, audit log, dan import Excel melalui staging + preview sebelum commit.
7. **Filter Global**: Penyaringan data berdasarkan Kecamatan, Kelurahan, Subsektor, Nama Narasumber, atau kata kunci lainnya yang berlaku di semua halaman.
8. **Keamanan P0**: Dashboard publik teragregasi, login dengan session aman, CSRF, rate-limit login, CORS allowlist, dan audit log.
9. **Halaman Survei Tahunan Ekraf**: Halaman `/survei` mandiri khusus admin untuk ringkasan, hasil clustering per pelaku, daftar anggota cluster, dan filter periode yang terpisah dari data spasial utama.

---

## 🛠️ Stack Teknologi

* **Backend**: Python 3.x, Flask, PostgreSQL Supabase
* **Frontend**: HTML5, CSS3, JavaScript (ES6), Bootstrap 5, Bootstrap Icons
* **Library Peta & Visualisasi**: Leaflet.js (dengan Leaflet.markercluster), Plotly.js
* **Library Pengolahan Data**: Pandas, NumPy, Scikit-learn (untuk DBSCAN), Openpyxl (ekspor/impor Excel)
* **Tabel**: DataTables

---

## 📂 Struktur Proyek

```text
dashboard-ekraf/
│
├── app.py                # Entry point utama aplikasi Flask
├── config.py             # Konstanta global, konfigurasi warna & DBSCAN
├── requirements.txt      # Daftar dependensi Python
├── MIGRASI.md            # Dokumentasi migrasi proyek dari Streamlit
├── README.md             # Dokumentasi proyek (file ini)
│
├── api/                  # Modul API Blueprint Flask
│   ├── __init__.py
│   ├── chart.py          # API untuk visualisasi grafik
│   ├── crud.py           # API untuk operasi database (Create, Read, Update, Delete)
│   ├── dashboard.py      # API untuk data ringkasan / KPI
│   ├── dbscan.py         # API untuk perhitungan clustering DBSCAN
│   ├── filter.py         # API untuk memproses data filter global
│   ├── table.py          # API untuk data tabel utama
│   └── upload.py         # API untuk upload berkas Excel
│
├── geojson/              # Batas wilayah administratif kecamatan
│   ├── Kota Malang.geojson
│   └── id35730*.geojson  # GeoJSON batas per kecamatan (Klojen, Lowokwaru, Blimbing, dll.)
│
├── static/               # File statis (CSS, JS, Gambar)
│   ├── css/
│   │   └── style.css     # Desain sistem kustom "Spatial Creative Index"
│   ├── js/
│   │   ├── app.js        # Controller navigasi halaman (SPA)
│   │   ├── dashboard.js  # Script inisialisasi peta utama, filter, & KPI
│   │   ├── clustering.js # Script visualisasi DBSCAN
│   │   ├── tabel.js      # Script manajemen DataTables
│   │   └── kelola.js     # Script operasi CRUD dan Upload
│   └── img/
│       └── logo.svg      # Logo instansi / aplikasi
│
├── templates/            # Template HTML Flask
│   ├── base.html         # Template induk (Sidebar, Header, Footer)
│   └── dashboard.html    # Halaman utama aplikasi (SPA container)
│
└── utils/                # Helper / Utilitas logika Python
    ├── __init__.py
    ├── clustering.py     # Logika pemrosesan algoritma DBSCAN
    ├── data_loader.py    # Helper untuk memuat dan menyaring data pelaku ekraf
    ├── filtering.py      # Logika pemfilteran global
    ├── helper.py         # Fungsi bantuan umum
    └── kpi.py            # Kalkulasi statistik KPI dashboard
```

---

## ⚙️ Cara Instalasi & Menjalankan Aplikasi

### 1. Clone Repositori
Clone repositori ini ke komputer lokal Anda:
```bash
git clone https://github.com/afrzlfaiz/flask-dashboard-ekraf.git
cd flask-dashboard-ekraf
```

### 2. Buat & Aktifkan Virtual Environment (Opsional tetapi Direkomendasikan)
Di macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```
Di Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependensi
Pasang seluruh pustaka Python yang dibutuhkan:
```bash
pip install -r requirements.txt
```

Salin konfigurasi contoh, lalu isi `DATABASE_URL` Supabase dan `SECRET_KEY`:

```bash
cp .env.example .env
```

### 4. Setup Database

Aplikasi membuat atau memperbarui tabel PostgreSQL secara otomatis saat startup. Data dikelola langsung melalui Supabase dan fitur impor XLSX di halaman Kelola Data.

Modul survei hanya dapat dibuka admin. Halaman `/survei` menampilkan daftar metadata periode, `/survei/periode-YYYY` menampilkan analisis satu tahun beserta hasil cluster per pelaku, dan `/survei/kelola` digunakan untuk menambah tahun berikutnya. Jawaban mentah tersimpan di `survey_responses`, sedangkan hasil RobustScaler + DBSCAN + PCA disiapkan satu kali saat import/backfill dan disimpan per pelaku di `survey_analysis_results`; hasil antar-tahun tidak digabung.

Periode awal 2026 dapat di-seed dari sheet `Sheet6` pada file `SURVEY_DATA_PATH` (default lokal: `../laporan/Data PKL Fix.xlsx`) menggunakan script import. Periode lama yang belum memiliki hasil analisis akan diproses satu kali saat pertama kali dibuka, lalu halaman hanya membaca hasil tersimpan dengan pagination maksimal 50 baris.

Untuk seed awal secara manual:
```bash
python scripts/import_survey.py --year 2026 --sheet Sheet6
```

### 5. Jalankan Aplikasi
Jalankan server Flask lokal:
```bash
python app.py
```
Setelah server berjalan, buka peramban (*browser*) Anda dan akses alamat:
`http://localhost:5000`

### 6. Buat Pengguna Internal

Aplikasi tidak menyediakan akun atau password default. Buat admin pertama secara interaktif:

```bash
python scripts/manage_users.py create nama_admin --role admin
```

Panduan konfigurasi production dan import tersedia di [SECURITY.md](SECURITY.md).

## Deploy ke Render dengan GHCR

Repository menyediakan `Dockerfile`, GitHub Actions, health check `/healthz`, dan `render.yaml`. Alurnya: test → build image → push ke GHCR → panggil Render Deploy Hook.

1. Push repository ke GitHub.
2. Buat **GitHub Personal Access Token** dengan izin `read:packages`.
3. Di Render tambahkan registry credential bernama `ghcr-dashboard-ekraf` untuk `ghcr.io`, menggunakan username GitHub dan token tersebut.
4. Di Render pilih **New → Blueprint**, lalu pilih repository ini. `render.yaml` akan menggunakan image `ghcr.io/afrzlfaiz/flask-dashboard-ekraf:latest`.
5. Isi `DATABASE_URL`, `BOOTSTRAP_ADMIN_USERNAME`, dan `BOOTSTRAP_ADMIN_PASSWORD` saat diminta. `SECRET_KEY` dibuat otomatis oleh Render.
6. Setelah admin pertama berhasil dibuat, kosongkan dua environment variable bootstrap admin.
7. Di Render buka **Settings → Deploy Hook**, buat hook baru, lalu simpan URL-nya di GitHub pada **Settings → Secrets and variables → Actions** dengan nama `RENDER_DEPLOY_HOOK_URL`.
8. Push ke branch `main`. GitHub Actions menggunakan `GITHUB_TOKEN` bawaan untuk push image ke GHCR, lalu memicu deploy Render.

Konfigurasi lain sudah memiliki default production yang aman. Auto-deploy Render dimatikan agar tidak terjadi deploy ganda; deployment dilakukan setelah image berhasil dipush ke GHCR dan hook dipanggil.

---

## 📄 Lisensi
Hak Cipta © 2026 BAPPEDA Kota Malang. Semua hak dilindungi undang-undang.
