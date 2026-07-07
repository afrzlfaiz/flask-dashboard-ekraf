Berikut adalah ringkasan proyek yang dapat Anda salin ke chat baru agar konteksnya langsung dipahami.

---

# Ringkasan Proyek

## Nama Proyek

**Dashboard Spasial Ekonomi Kreatif Kota Malang**

Tujuan proyek adalah mengembangkan dashboard web profesional untuk visualisasi persebaran pelaku ekonomi kreatif Kota Malang menggunakan Python sebagai backend dan database SQLite.

Awalnya proyek dibuat menggunakan **Streamlit**, namun akan dimigrasikan menjadi aplikasi berbasis **Flask + HTML + CSS + JavaScript** dengan tampilan modern menyerupai website pemerintahan.

---

# Target Akhir

Membangun aplikasi web profesional yang memiliki tampilan seperti dashboard pemerintahan (Bappenas, BPS, Kemendagri, dll), dengan tema terang (light theme), responsive, dan modern.

Stack yang digunakan:

* Backend

  * Flask
  * Python
  * SQLite

* Frontend

  * HTML5
  * Bootstrap 5
  * CSS3
  * JavaScript ES6

* Visualisasi

  * Plotly.js
  * Leaflet.js

* Tabel

  * DataTables

---

# Tema UI

Tema yang diinginkan:

* Light Theme
* Dominan putih
* Biru sebagai warna utama
* Banyak whitespace
* Card dengan rounded corner
* Shadow lembut
* Modern Government Dashboard
* Responsive
* Flat design
* Animasi ringan
* Profesional, bukan template admin gelap

Referensi visual menyerupai dashboard pemerintah modern.

---

# Arsitektur

```text
Browser

↓

HTML
CSS
JavaScript

↓

Flask

↓

Python

↓

SQLite
```

Semua analisis tetap menggunakan Python.

---

# Struktur Folder yang Diinginkan

```text
dashboard-ekraf/

app.py

config.py

requirements.txt

database/
    ekraf.db

templates/
    base.html
    dashboard.html
    clustering.html
    table.html
    manage.html

static/

    css/

    js/

    img/

    vendor/

api/

utils/

geojson/
```

---

# Halaman yang Harus Ada

## 1 Dashboard

Halaman utama.

Isi:

* KPI Cards
* Filter
* Peta Interaktif
* Grafik
* Heatmap
* Top Kecamatan
* Top Kelurahan

---

## 2 Peta Persebaran

Berisi

* Leaflet
* Marker
* Popup
* Google Maps
* Overlay GeoJSON
* Legend
* Fullscreen

---

## 3 Analisis DBSCAN

Berisi

* Parameter DBSCAN

  * eps

  * min_samples

* Tombol proses clustering

* Hasil cluster

* Peta cluster

* Statistik cluster

* Ringkasan cluster

---

## 4 Statistik

Berisi berbagai visualisasi:

* Bar Chart
* Pie Chart
* Donut Chart
* Line Chart
* Heatmap
* Histogram
* Distribusi subsektor
* Distribusi kecamatan
* Distribusi kelurahan

---

## 5 Tabel Data

Berisi

* Search
* Sort
* Pagination
* Export Excel
* Export CSV

---

## 6 Kelola Data

CRUD

* Upload Excel
* Preview
* Tambah
* Edit
* Hapus
* Simpan

---

# Sidebar

Sidebar modern.

Menu:

Dashboard

Peta Persebaran

Analisis DBSCAN

Statistik

Tabel Data

Kelola Data

Pengaturan

Tentang

---

# Header

Berisi

Logo BAPPEDA

Judul Dashboard

Breadcrumb

Tanggal

Refresh

Profil Admin

---

# Footer

Berisi

Copyright

Versi aplikasi

---

# Filter Global

Semua halaman menggunakan filter yang sama.

Filter:

Kecamatan

Kelurahan

Subsektor

Nama Narasumber

Keyword

Reset Filter

Apply Filter

---

# KPI Cards

Minimal berisi:

Total Pelaku

Jumlah Kecamatan

Jumlah Kelurahan

Jumlah Subsektor

Jumlah Data Valid

---

# Peta

Menggunakan Leaflet.

Fitur:

Marker

Marker Cluster

Popup

Google Maps

GeoJSON Kota

GeoJSON Kecamatan

Legend

Layer Control

Zoom

Fullscreen

Search

---

# Grafik

Menggunakan Plotly.

Minimal:

Bar Chart

Pie Chart

Donut

Line

Heatmap

Treemap (opsional)

---

# Tabel

Menggunakan DataTables.

Fitur:

Search

Pagination

Sorting

Export

Responsive

---

# Database

SQLite

CRUD lengkap

Import Excel

Update

Delete

Insert

---

# API Flask

Contoh endpoint:

```text
/api/dashboard

/api/map

/api/filter

/api/dbscan

/api/chart

/api/table

/api/crud

/api/upload
```

Semua mengembalikan JSON.

---

# Variabel Data

Dataset ekonomi kreatif minimal memiliki variabel berikut:

## Identitas

* id
* nama_narasumber
* nama_usaha

## Lokasi

* kecamatan
* kelurahan
* alamat
* latitude
* longitude

## Ekonomi Kreatif

* subsektor
* kategori_usaha
* produk
* tahun_berdiri

## Kontak

* no_hp
* email
* media_sosial (opsional)

## Analisis

* cluster_dbscan
* status_noise
* jumlah_tetangga (opsional)

---

# Analisis DBSCAN

Input:

latitude

longitude

eps

min_samples

Output:

cluster

noise

jumlah cluster

jumlah anggota cluster

persentase noise

visualisasi cluster

---

# Fitur yang Harus Dipertahankan dari Streamlit

* Filter data
* KPI
* Peta interaktif
* Overlay batas wilayah
* Heatmap
* Grafik distribusi
* Top Kecamatan
* Top Kelurahan
* DBSCAN
* CRUD
* Upload Excel
* SQLite
* Export data
* Google Maps

---

# Prototype Awal

Sebelum migrasi penuh ke Flask, buat satu file **SPA (Single Page Application)** bernama **`prototype.html`**.

Ketentuan:

* Seluruh HTML, CSS, dan JavaScript berada dalam satu file.
* Tidak menggunakan backend.
* Menampilkan seluruh halaman dalam bentuk mockup interaktif dengan navigasi SPA (tanpa reload).
* Menggunakan Bootstrap 5, Bootstrap Icons, Plotly.js, Leaflet.js, dan DataTables melalui CDN.
* Menampilkan data dummy yang realistis.
* Desain harus menyerupai dashboard pemerintahan modern dengan tema terang (putih–biru), rounded cards, shadow lembut, responsive, dan siap dijadikan dasar migrasi ke Flask.

---

# Tujuan Akhir

Menghasilkan aplikasi web yang tampilannya setara dashboard profesional pemerintahan, tetapi seluruh logika analisis (filter, visualisasi, DBSCAN, CRUD, SQLite) tetap dijalankan menggunakan Python melalui Flask sebagai backend.
