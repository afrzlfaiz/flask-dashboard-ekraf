# Dashboard Spasial Ekonomi Kreatif Kota Malang

Dashboard web interaktif untuk visualisasi dan analisis spasial persebaran pelaku Ekonomi Kreatif (Ekraf) di Kota Malang. Aplikasi ini dibangun menggunakan **Flask** sebagai backend, **SQLite** sebagai database, dan visualisasi spasial interaktif menggunakan **Leaflet.js** serta analisis clustering menggunakan algoritma **DBSCAN (scikit-learn)**.

Aplikasi ini dirancang dengan gaya **Modern Government Dashboard** bertema terang (*light theme*), mengutamakan *whitespace*, sudut melengkung (*rounded corners*), bayangan lembut (*soft shadows*), serta tata letak yang responsif.

---

## 🚀 Fitur Utama

1. **Dashboard & KPI Cards**: Ringkasan data penting seperti Total Pelaku Ekraf, Jumlah Kecamatan/Kelurahan, Jumlah Subsektor, dan data valid.
2. **Peta Persebaran Interaktif**: Visualisasi spasial berbasis **Leaflet.js** dengan marker cluster, popup info detail, overlay batas wilayah menggunakan GeoJSON tingkat kecamatan Kota Malang, legenda, dan opsi basemap Google Maps.
3. **Analisis Spasial DBSCAN**: Fitur pengelompokan wilayah (*clustering*) secara *real-time* berdasarkan koordinat geografis (latitude & longitude) menggunakan algoritma DBSCAN dengan parameter dinamis (`eps` dan `min_samples`). Menghasilkan peta klaster dan analisis persentase *noise*.
4. **Statistik & Visualisasi**: Berbagai chart interaktif menggunakan **Plotly.js** untuk menunjukkan distribusi subsektor, kecamatan, kelurahan, dan kategori usaha.
5. **Tabel Data Interaktif**: Pencarian, pengurutan (*sorting*), paginasi data menggunakan **DataTables**, serta fitur ekspor data ke Excel dan CSV.
6. **Kelola Data (CRUD)**: Manajemen data pelaku ekraf (Tambah, Edit, Hapus) beserta fitur **Import Excel** untuk memperbarui database secara massal.
7. **Filter Global**: Penyaringan data berdasarkan Kecamatan, Kelurahan, Subsektor, Nama Narasumber, atau kata kunci lainnya yang berlaku di semua halaman.

---

## 🛠️ Stack Teknologi

* **Backend**: Python 3.x, Flask, SQLite3
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
├── data/                 # Penyimpanan data (diabaikan dari Git)
│   ├── ekraf.xlsx        # File sumber data asli (tidak disertakan di repositori)
│   ├── ekraf.db          # Database SQLite hasil migrasi (tidak disertakan di repositori)
│   └── migrate_to_db.py  # Skrip migrasi data dari Excel ke SQLite
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

### 4. Setup Data & Database (Penting)
Repositori ini **tidak menyertakan database (`ekraf.db`) dan data Excel asli (`ekraf.xlsx`)** demi keamanan dan efisiensi ukuran repositori.

Silakan ikuti langkah berikut untuk menginisialisasi data:
1. Siapkan file data Excel Anda dan beri nama **`ekraf.xlsx`**.
2. Letakkan file `ekraf.xlsx` tersebut ke dalam folder **`data/`** di proyek Anda.
3. Jalankan skrip migrasi untuk membuat database SQLite secara otomatis:
   ```bash
   python data/migrate_to_db.py
   ```
   Skrip ini akan membuat file **`ekraf.db`** di dalam folder `data/` yang berisi tabel pelaku ekraf.

### 5. Jalankan Aplikasi
Jalankan server Flask lokal:
```bash
python app.py
```
Setelah server berjalan, buka peramban (*browser*) Anda dan akses alamat:
`http://localhost:5000`

---

## 📄 Lisensi
Hak Cipta © 2026 BAPPEDA Kota Malang. Semua hak dilindungi undang-undang.
