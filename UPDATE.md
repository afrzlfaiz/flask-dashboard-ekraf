# UPDATE.md

# Rekomendasi Perbaikan Dashboard Spasial Ekonomi Kreatif Kota Malang

Dokumen ini berisi roadmap perbaikan proyek **Dashboard Spasial Ekonomi Kreatif Kota Malang** berdasarkan tingkat urgensi, risiko, dan dampaknya terhadap keamanan, kualitas data, kestabilan aplikasi, serta kesiapan implementasi di lingkungan BAPPEDA.

Urutan prioritas:

1. **P0 — Kritis / wajib sebelum deployment**
2. **P1 — Tinggi / wajib untuk operasional**
3. **P2 — Menengah / peningkatan kualitas analisis**
4. **P3 — Lanjutan / pengembangan strategis**

---

## Ringkasan Prioritas

| Prioritas | Fokus | Tujuan |
|---|---|---|
| P0 | Keamanan dan perlindungan data | Mencegah akses tidak sah, kebocoran data, dan kerusakan database |
| P1 | Validasi dan tata kelola data | Menjamin data yang ditampilkan benar, konsisten, dan dapat dipertanggungjawabkan |
| P2 | Analisis spasial dan performa | Meningkatkan kualitas interpretasi, kecepatan, dan skalabilitas |
| P3 | Sistem pendukung keputusan | Mengubah dashboard menjadi alat rekomendasi kebijakan |

---

# P0 — KRITIS

Perbaikan berikut harus diselesaikan sebelum aplikasi digunakan pada server publik atau diakses banyak pengguna.

> **Status 17 Juli 2026:** seluruh checklist P0 telah diimplementasikan dan diverifikasi melalui `python -m unittest discover -s tests -v`. Detail operasional tersedia di `SECURITY.md`.

---

## 1. Nonaktifkan Debug Mode pada Production

### Masalah

Aplikasi Flask tidak boleh dijalankan dengan:

```python
app.run(debug=True, host="0.0.0.0")
```

Debug mode dapat membocorkan informasi internal aplikasi dan meningkatkan risiko eksploitasi.

### Perbaikan

Gunakan konfigurasi berbasis environment:

```python
import os

DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
```

Pada `app.py`:

```python
if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", 5000)),
        debug=DEBUG
    )
```

### Checklist

- [x] Debug mode aktif hanya pada development
- [x] Production menggunakan `debug=False`
- [x] Tidak ada traceback yang ditampilkan ke pengguna
- [x] Error teknis disimpan di server log

---

## 2. Tambahkan Autentikasi Pengguna

### Masalah

Endpoint CRUD, upload, dan ekspor dapat berisiko diakses tanpa autentikasi.

### Rekomendasi

Gunakan:

- `Flask-Login` untuk autentikasi dasar; atau
- Single Sign-On apabila tersedia pada lingkungan pemerintah.

### Role yang Disarankan

| Role | Hak Akses |
|---|---|
| Viewer | Melihat dashboard dan data agregat |
| Operator | Menambah dan memperbarui data |
| Validator | Memvalidasi data dan hasil impor |
| Admin | Mengelola pengguna, menghapus data, dan melakukan impor massal |

### Checklist

- [x] Halaman login tersedia
- [x] Password disimpan menggunakan hashing
- [x] Session cookie menggunakan konfigurasi aman
- [x] Endpoint admin wajib login
- [x] Hak akses diperiksa pada setiap endpoint sensitif
- [x] Logout dan session timeout tersedia

---

## 3. Pisahkan Dashboard Publik dan Internal

### Masalah

Data pelaku ekraf dapat mengandung:

- nama narasumber;
- nomor telepon;
- email;
- alamat lengkap;
- koordinat lokasi presisi.

Data tersebut tidak seharusnya ditampilkan secara terbuka tanpa pengaturan hak akses.

### Rekomendasi

#### Dashboard Publik

Hanya menampilkan:

- data agregat;
- jumlah pelaku per wilayah;
- statistik subsektor;
- peta choropleth;
- koordinat yang telah digeneralisasi atau diagregasi.

#### Dashboard Internal

Dapat menampilkan:

- identitas pelaku;
- kontak;
- koordinat presisi;
- CRUD;
- impor data;
- validasi;
- audit log.

### Checklist

- [x] Endpoint publik dan internal dipisahkan
- [x] Data pribadi tidak muncul pada dashboard publik
- [x] Koordinat publik diagregasi atau dibuat kurang presisi
- [x] Ekspor data mentah hanya tersedia untuk pengguna berwenang

---

## 4. Lindungi Endpoint CRUD

### Masalah

Operasi tambah, edit, dan hapus data dapat merusak database apabila tidak dilindungi.

### Rekomendasi

Tambahkan:

- autentikasi;
- role-based access control;
- validasi input;
- proteksi CSRF;
- transaksi database;
- audit log.

### Checklist

- [x] Create hanya untuk Operator, Validator, atau Admin
- [x] Update mencatat pengguna dan waktu perubahan
- [x] Delete hanya untuk Admin
- [x] Penghapusan menggunakan soft delete
- [x] Semua perubahan memiliki histori
- [x] Input wajib divalidasi sebelum disimpan

---

## 5. Gunakan Soft Delete

### Masalah

Penghapusan permanen membuat data sulit dipulihkan dan menghilangkan jejak administrasi.

### Perbaikan

Tambahkan kolom:

```sql
is_active INTEGER DEFAULT 1,
deleted_at DATETIME NULL,
deleted_by INTEGER NULL
```

Data tidak langsung dihapus, tetapi dinonaktifkan.

### Checklist

- [x] Tombol hapus mengubah `is_active`
- [x] Data terhapus tidak muncul pada dashboard utama
- [x] Admin dapat memulihkan data
- [x] Penghapusan permanen hanya dilakukan melalui prosedur khusus

---

## 6. Batasi dan Validasi Upload Excel

### Masalah

Upload saat ini berpotensi menerima:

- file terlalu besar;
- struktur kolom salah;
- data dengan format tidak valid;
- file dengan ekstensi palsu;
- duplikat dalam jumlah besar.

### Rekomendasi

Tambahkan validasi:

- ukuran file maksimum;
- MIME type;
- ekstensi;
- jumlah baris;
- kolom wajib;
- tipe data;
- format koordinat;
- nilai referensi kecamatan, kelurahan, dan subsektor.

### Contoh Konfigurasi

```python
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
```

### Checklist

- [x] Maksimum ukuran file ditentukan
- [x] Hanya `.xlsx` yang diterima
- [x] MIME type diperiksa
- [x] Kolom wajib diperiksa
- [x] File tidak langsung masuk ke tabel utama
- [x] Tersedia preview sebelum impor
- [x] Proses impor dapat di-rollback
- [x] Hasil impor menampilkan jumlah valid, gagal, dan duplikat

---

## 7. Hapus Traceback dari Respons API

### Masalah

Traceback dapat membocorkan:

- struktur folder;
- nama file;
- query;
- library;
- detail internal aplikasi.

### Perbaikan

Respons pengguna:

```json
{
  "success": false,
  "message": "Terjadi kesalahan saat memproses data."
}
```

Detail teknis disimpan melalui logger:

```python
current_app.logger.exception("Upload gagal")
```

### Checklist

- [x] Tidak ada traceback pada JSON response
- [x] Log error tersedia di server
- [x] Error memiliki kode referensi
- [x] Pesan error mudah dipahami pengguna

---

## 8. Batasi CORS

### Masalah

Konfigurasi `CORS(app)` membuka akses dari seluruh origin.

### Perbaikan

Gunakan daftar domain yang diizinkan:

```python
CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "https://ekraf.malangkota.go.id"
            ]
        }
    }
)
```

### Checklist

- [x] Origin production ditentukan
- [x] Development origin dipisahkan
- [x] Credential hanya diaktifkan bila diperlukan
- [x] Endpoint admin tidak terbuka lintas origin tanpa kontrol

---

## 9. Amankan Konfigurasi Aplikasi

### Rekomendasi

Pindahkan konfigurasi sensitif ke `.env`:

```env
SECRET_KEY=
DATABASE_URL=
FLASK_ENV=
ALLOWED_ORIGINS=
MAX_UPLOAD_SIZE=
```

Tambahkan `.env` ke `.gitignore`.

### Checklist

- [x] Secret key tidak ditulis langsung di source code
- [x] File `.env` tidak masuk Git
- [x] Tersedia `.env.example`
- [x] Development dan production memiliki konfigurasi berbeda

---

## 10. Tambahkan Backup Database

### Masalah

SQLite mudah dicadangkan, tetapi tetap membutuhkan prosedur rutin.

### Checklist

- [x] Backup otomatis harian
- [x] Backup diberi timestamp
- [x] Backup disimpan di lokasi terpisah
- [x] Retensi backup ditentukan
- [x] Prosedur restore diuji
- [x] Backup dilakukan sebelum impor massal

---

# P1 — PRIORITAS TINGGI

Perbaikan berikut diperlukan agar data dapat dipakai secara operasional dan dipertanggungjawabkan.

---

## 11. Buat Workflow Verifikasi Data

### Tambahkan Kolom

```sql
verification_status TEXT DEFAULT 'draft',
verified_by INTEGER NULL,
verified_at DATETIME NULL,
verification_notes TEXT NULL
```

### Status yang Disarankan

- `draft`
- `pending`
- `verified`
- `rejected`
- `needs_revision`

### Checklist

- [ ] Data baru berstatus draft
- [ ] Operator mengirim data untuk verifikasi
- [ ] Validator dapat menerima atau menolak
- [ ] Hanya data verified masuk statistik resmi
- [ ] Alasan penolakan tersimpan

---

## 12. Tambahkan Metadata Data

Setiap record sebaiknya memiliki:

```text
created_at
created_by
updated_at
updated_by
source
survey_year
import_batch_id
is_active
verification_status
```

### Tujuan

- mengetahui asal data;
- melacak perubahan;
- membedakan data lama dan baru;
- mendukung audit;
- mendukung analisis temporal.

---

## 13. Buat Master Data

Gunakan tabel referensi untuk:

- kecamatan;
- kelurahan;
- subsektor;
- kategori usaha;
- status usaha;
- jenis legalitas.

### Struktur Dasar

```sql
CREATE TABLE kecamatan (
    id INTEGER PRIMARY KEY,
    nama TEXT UNIQUE NOT NULL
);
```

### Checklist

- [ ] Tidak menggunakan input teks bebas untuk wilayah
- [ ] Kelurahan terkait dengan kecamatan
- [ ] Subsektor menggunakan referensi resmi
- [ ] Dropdown mengambil data dari master
- [ ] Nilai lama dimigrasikan ke format master

---

## 14. Validasi Koordinat

### Validasi Minimum

- latitude dan longitude numerik;
- tidak bernilai nol;
- berada dalam bounding box Kota Malang;
- titik berada dalam polygon Kota Malang;
- titik sesuai dengan kecamatan/kelurahan yang dipilih.

### Status Koordinat

```text
valid
outside_city
mismatch_area
missing
suspected_duplicate
```

### Checklist

- [ ] Point-in-polygon diterapkan
- [ ] Koordinat di luar kota ditandai
- [ ] Perbedaan wilayah administratif ditampilkan
- [ ] Peta menyediakan fitur koreksi titik

---

## 15. Perbaiki Deteksi Duplikat

### Jangan Hanya Menggunakan

```text
Nama Narasumber + Sub Sektor
```

### Gunakan Kombinasi

- nama usaha ternormalisasi;
- alamat ternormalisasi;
- nomor telepon;
- subsektor;
- kecamatan/kelurahan;
- jarak koordinat.

### Rekomendasi

Gunakan status:

```text
potential_duplicate
```

Data tidak langsung dihapus, tetapi dikirim ke halaman validasi.

### Checklist

- [ ] Normalisasi huruf besar dan kecil
- [ ] Normalisasi spasi dan tanda baca
- [ ] Normalisasi nomor telepon
- [ ] Fuzzy matching diterapkan
- [ ] Jarak koordinat menjadi salah satu indikator
- [ ] Validator memutuskan merge atau tetap terpisah

---

## 16. Buat Halaman Kualitas Data

### KPI yang Disarankan

- total record;
- data terverifikasi;
- koordinat valid;
- koordinat kosong;
- data di luar Kota Malang;
- potensi duplikat;
- kontak tidak valid;
- data lama;
- data belum lengkap.

### Tujuan

Dashboard tidak hanya menampilkan data ekonomi kreatif, tetapi juga menunjukkan tingkat kepercayaan terhadap data tersebut.

---

## 17. Gunakan Staging Table untuk Import

### Alur

```text
Upload
→ Validasi
→ Staging
→ Preview
→ Persetujuan
→ Commit ke database utama
```

### Struktur

```sql
import_batches
import_staging
import_errors
```

### Checklist

- [ ] Setiap upload mempunyai batch ID
- [ ] Data gagal tidak masuk tabel utama
- [ ] Pengguna dapat membatalkan batch
- [ ] Hasil validasi dapat diunduh
- [ ] Batch yang sudah diimpor memiliki histori

---

## 18. Tambahkan Audit Log

### Simpan Informasi

```text
user_id
action
entity
entity_id
old_value
new_value
timestamp
ip_address
```

### Aktivitas yang Dicatat

- login;
- tambah data;
- edit data;
- hapus data;
- restore data;
- upload;
- validasi;
- ekspor.

---

## 19. Definisikan KPI Secara Formal

Setiap KPI harus mempunyai:

- nama;
- definisi;
- formula;
- sumber data;
- filter yang berlaku;
- periode data;
- penanggung jawab.

### Contoh

**Data Valid**

Record yang:

- berstatus verified;
- memiliki koordinat valid;
- memiliki kecamatan dan kelurahan sesuai;
- memiliki subsektor resmi;
- memiliki tahun pendataan;
- tidak dinonaktifkan.

---

# P2 — PRIORITAS MENENGAH

Perbaikan berikut meningkatkan kualitas analisis, pengalaman pengguna, dan performa.

---

## 20. Ubah Parameter DBSCAN Menjadi Meter

### Masalah

Pengguna sulit memahami nilai derajat seperti `0.008`.

### API yang Disarankan

```json
{
  "eps_meters": 500,
  "min_samples": 4
}
```

### Konversi

```python
EARTH_RADIUS_METERS = 6_371_000
eps_radians = eps_meters / EARTH_RADIUS_METERS
```

### Checklist

- [ ] UI menggunakan satuan meter
- [ ] Nilai minimum dan maksimum dibatasi
- [ ] Tooltip menjelaskan fungsi parameter
- [ ] Preset parameter tersedia

---

## 21. Tambahkan Preset DBSCAN

### Contoh

| Preset | Radius | Minimum Titik | Tujuan |
|---|---:|---:|---|
| Mikro | 250 m | 3 | Konsentrasi sangat lokal |
| Lokal | 500 m | 4 | Konsentrasi lingkungan |
| Kawasan | 1.000 m | 5 | Konsentrasi lintas kelurahan |

Pengguna tetap dapat memilih parameter manual.

---

## 22. Tambahkan Analisis Sensitivitas

Tampilkan perbandingan beberapa parameter:

```text
300 meter → 18 klaster, noise 42%
500 meter → 10 klaster, noise 21%
700 meter → 6 klaster, noise 10%
```

### Tujuan

Mencegah pengguna menganggap satu parameter sebagai satu-satunya hasil yang benar.

---

## 23. Perbaiki Definisi “Parameter Optimal”

Jangan hanya menggunakan silhouette score.

Gunakan kombinasi:

- silhouette score;
- persentase noise;
- jumlah klaster;
- ukuran klaster minimum;
- stabilitas hasil;
- validasi administratif;
- penilaian pakar.

Tambahkan disclaimer:

> Hasil klaster menunjukkan konsentrasi spasial berdasarkan data yang tersedia dan tidak secara otomatis menunjukkan tingkat keberhasilan ekonomi suatu wilayah.

---

## 24. Gunakan Medoid dan Polygon Klaster

Rata-rata koordinat dapat berada di lokasi yang tidak mewakili klaster.

### Rekomendasi

- gunakan medoid sebagai pusat representatif;
- buat convex hull atau concave hull;
- tampilkan luas area klaster;
- tampilkan subsektor dominan pada klaster.

---

## 25. Tambahkan Choropleth

Peta choropleth sebaiknya tersedia berdasarkan:

- jumlah pelaku;
- kepadatan per km²;
- persentase data valid;
- subsektor dominan;
- indeks keragaman;
- pertumbuhan tahunan.

Hindari hanya menggunakan jumlah mentah.

---

## 26. Tambahkan Normalisasi Wilayah

Gunakan indikator:

```text
pelaku per km²
pelaku per 1.000 penduduk
pelaku per 1.000 penduduk usia produktif
```

### Tujuan

Mencegah wilayah luas atau padat mendominasi interpretasi hanya karena jumlah absolut.

---

## 27. Optimalkan Query Database

### Masalah

Membaca seluruh tabel ke Pandas pada setiap request akan melambat saat data bertambah.

### Perbaikan

- filtering melalui SQL;
- gunakan `LIMIT` dan `OFFSET`;
- gunakan server-side pagination;
- pilih kolom yang diperlukan;
- buat index database.

### Index yang Disarankan

```sql
CREATE INDEX idx_ekraf_kecamatan ON pelaku_ekraf(kecamatan_id);
CREATE INDEX idx_ekraf_kelurahan ON pelaku_ekraf(kelurahan_id);
CREATE INDEX idx_ekraf_subsektor ON pelaku_ekraf(subsektor_id);
CREATE INDEX idx_ekraf_status ON pelaku_ekraf(verification_status);
```

---

## 28. Terapkan Server-Side DataTables

Endpoint tabel sebaiknya menerima:

```text
page
page_size
search
sort_by
sort_order
filters
```

Respons:

```json
{
  "data": [],
  "total": 1000,
  "filtered": 125,
  "page": 1
}
```

---

## 29. Tambahkan Caching

Data berikut dapat di-cache:

- KPI;
- daftar kecamatan;
- daftar kelurahan;
- daftar subsektor;
- agregasi chart;
- hasil DBSCAN berdasarkan parameter dan versi data.

Cache harus dihapus ketika data berubah.

---

## 30. Migrasi ke PostgreSQL/PostGIS

Migrasi direkomendasikan apabila:

- pengguna bertambah;
- perubahan data semakin sering;
- aplikasi diakses lintas perangkat;
- ukuran data meningkat;
- analisis spasial bertambah kompleks.

### Manfaat

- transaksi lebih kuat;
- akses multiuser;
- spatial index;
- point-in-polygon;
- query jarak;
- agregasi spasial;
- backup lebih baik.

---

## 31. Gunakan SQLAlchemy dan Alembic

### Tujuan

- skema lebih konsisten;
- query lebih aman;
- migrasi database terdokumentasi;
- pengembangan lebih mudah.

### Checklist

- [ ] Model database tersedia
- [ ] Migration history tersedia
- [ ] Foreign key digunakan
- [ ] Constraint diterapkan
- [ ] Nama kolom menggunakan `snake_case`

---

## 32. Tambahkan Automated Testing

### Struktur

```text
tests/
├── test_auth.py
├── test_permissions.py
├── test_crud.py
├── test_upload.py
├── test_filters.py
├── test_dbscan.py
├── test_validation.py
└── test_export.py
```

### Skenario Wajib

- pengguna tanpa login mengakses admin;
- viewer mencoba menghapus;
- upload tanpa kolom wajib;
- upload terlalu besar;
- koordinat di luar kota;
- parameter DBSCAN invalid;
- rollback saat impor gagal;
- potensi duplikat;
- filter gabungan;
- ekspor data dengan hak akses.

---

## 33. Siapkan Deployment Production

### Arsitektur

```text
Nginx
  ↓
Gunicorn / Waitress
  ↓
Flask
  ↓
PostgreSQL / PostGIS
```

### Checklist

- [ ] Dockerfile tersedia
- [ ] Gunicorn atau Waitress digunakan
- [ ] HTTPS aktif
- [ ] Health check tersedia
- [ ] Logging terstruktur
- [ ] Monitoring error tersedia
- [ ] Backup otomatis tersedia
- [ ] Staging environment tersedia

---

# P3 — PENGEMBANGAN LANJUTAN

Tahap ini berfokus pada peningkatan nilai dashboard sebagai sistem pendukung keputusan.

---

## 34. Tambahkan Profil Wilayah

Setiap kecamatan atau kelurahan memiliki halaman profil:

- jumlah pelaku;
- kepadatan;
- subsektor dominan;
- keragaman subsektor;
- kategori usaha;
- umur usaha;
- kualitas data;
- klaster terkait;
- perbandingan dengan rata-rata kota.

---

## 35. Tambahkan Analisis Temporal

Simpan snapshot atau histori berdasarkan tahun.

### Analisis

- pertumbuhan jumlah pelaku;
- usaha baru;
- usaha tidak aktif;
- perubahan subsektor;
- perubahan konsentrasi;
- dampak program pemerintah;
- perkembangan kualitas data.

---

## 36. Bangun Spatial Creative Economy Index

Contoh formula awal:

```text
30% kepadatan pelaku
20% keragaman subsektor
20% proporsi usaha aktif
15% kematangan usaha
15% kualitas data
```

Formula harus:

- transparan;
- terdokumentasi;
- dapat diuji;
- ditinjau bersama pemangku kebijakan.

---

## 37. Tambahkan Analisis Kesenjangan Layanan

Integrasikan data:

- ruang kreatif;
- sentra UMKM;
- pasar;
- perguruan tinggi;
- pusat pelatihan;
- fasilitas digital;
- transportasi;
- program bantuan.

### Pertanyaan yang Dijawab

- klaster mana yang belum memiliki fasilitas pendukung;
- wilayah mana yang membutuhkan pelatihan;
- subsektor apa yang belum terlayani;
- lokasi mana yang cocok untuk creative hub.

---

## 38. Tambahkan Rekomendasi Berbasis Aturan

Contoh:

```text
Jika jumlah pelaku tinggi
dan legalitas rendah
→ rekomendasi fasilitasi NIB.

Jika klaster kuliner besar
dan akses pelatihan rendah
→ rekomendasi pelatihan keamanan pangan.

Jika subsektor beragam
dan dekat perguruan tinggi
→ kandidat pengembangan creative hub.

Jika data lama dan kontak tidak lengkap
→ prioritas verifikasi ulang.
```

Setiap rekomendasi harus menampilkan:

- dasar indikator;
- nilai indikator;
- alasan rekomendasi;
- tingkat prioritas;
- wilayah sasaran.

---

## 39. Tambahkan Laporan Otomatis

Sediakan ekspor:

- PDF ringkasan eksekutif;
- Excel data terfilter;
- laporan profil wilayah;
- laporan hasil clustering;
- laporan kualitas data;
- laporan rekomendasi kebijakan.

---

## 40. Tingkatkan Aksesibilitas UX

### Checklist

- [ ] Kontras warna memenuhi standar
- [ ] Tidak hanya mengandalkan warna
- [ ] Keyboard navigation tersedia
- [ ] Label form jelas
- [ ] Error form spesifik
- [ ] Peta memiliki alternatif tabel
- [ ] Loading state tersedia
- [ ] Empty state tersedia
- [ ] Tampilan mobile diuji

---

# Rekomendasi Struktur Folder Setelah Pengembangan

```text
dashboard-ekraf/
├── app/
│   ├── __init__.py
│   ├── models/
│   ├── routes/
│   │   ├── public.py
│   │   ├── dashboard.py
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── upload.py
│   │   └── analysis.py
│   ├── services/
│   │   ├── clustering_service.py
│   │   ├── import_service.py
│   │   ├── validation_service.py
│   │   ├── recommendation_service.py
│   │   └── export_service.py
│   ├── repositories/
│   ├── schemas/
│   ├── templates/
│   └── static/
├── migrations/
├── tests/
├── scripts/
├── data/
├── docker/
├── config.py
├── requirements.in
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

# Rencana Implementasi yang Disarankan

## Sprint 1 — Keamanan Dasar

- [ ] Nonaktifkan debug production
- [ ] Tambahkan autentikasi
- [ ] Tambahkan role pengguna
- [ ] Lindungi endpoint admin
- [ ] Batasi CORS
- [ ] Aktifkan CSRF
- [ ] Hapus traceback dari response
- [ ] Buat konfigurasi `.env`

## Sprint 2 — Keamanan Data dan Import

- [ ] Pisahkan dashboard publik dan internal
- [ ] Batasi data pribadi
- [ ] Tambahkan validasi upload
- [ ] Tambahkan staging import
- [ ] Tambahkan transaksi dan rollback
- [ ] Tambahkan backup otomatis

## Sprint 3 — Tata Kelola Data

- [ ] Tambahkan status verifikasi
- [ ] Tambahkan metadata
- [ ] Buat master wilayah dan subsektor
- [ ] Validasi koordinat
- [ ] Tingkatkan deteksi duplikat
- [ ] Tambahkan audit log

## Sprint 4 — Analisis dan Performa

- [ ] Ubah DBSCAN menjadi meter
- [ ] Tambahkan preset dan sensitivity analysis
- [ ] Tambahkan choropleth
- [ ] Terapkan server-side pagination
- [ ] Optimalkan query
- [ ] Tambahkan caching

## Sprint 5 — Production Readiness

- [ ] Migrasi PostgreSQL/PostGIS
- [ ] Gunakan SQLAlchemy dan Alembic
- [ ] Tambahkan automated testing
- [ ] Tambahkan Docker
- [ ] Gunakan Gunicorn atau Waitress
- [ ] Siapkan staging dan monitoring

## Sprint 6 — Decision Support

- [ ] Profil wilayah
- [ ] Analisis temporal
- [ ] Spatial Creative Economy Index
- [ ] Analisis kesenjangan layanan
- [ ] Rekomendasi kebijakan berbasis aturan
- [ ] Laporan otomatis

---

# Definition of Done

Sebuah fitur dianggap selesai apabila:

- [ ] memiliki validasi input;
- [ ] memiliki kontrol hak akses;
- [ ] memiliki pesan error yang aman;
- [ ] memiliki logging;
- [ ] memiliki test;
- [ ] memiliki dokumentasi;
- [ ] diuji pada desktop dan mobile;
- [ ] tidak membocorkan data pribadi;
- [ ] telah melewati review kode;
- [ ] dapat dijalankan pada staging environment.

---

# Target Akhir

Dashboard ini diarahkan menjadi:

> **Sistem pendukung keputusan berbasis spasial untuk memantau, memvalidasi, dan menentukan prioritas pengembangan ekonomi kreatif di Kota Malang.**

Urutan pengembangan utama:

```text
Keamanan
→ Perlindungan data
→ Validasi dan tata kelola
→ Kualitas analisis spasial
→ Performa dan skalabilitas
→ Rekomendasi kebijakan
```

Penambahan grafik baru sebaiknya tidak menjadi prioritas sebelum keamanan, kualitas data, dan tata kelola sistem diselesaikan.
