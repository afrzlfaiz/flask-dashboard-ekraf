# Operasional Keamanan P0

## Konfigurasi production

Production wajib menyediakan `SECRET_KEY`, `ALLOWED_ORIGINS`, dan `BACKUP_DIR` melalui environment. Gunakan HTTPS dan set:

```env
FLASK_ENV=production
FLASK_DEBUG=false
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax
```

Aplikasi menolak startup production jika debug aktif, secret masih placeholder, origin kosong, atau lokasi backup belum ditentukan.

## Pengguna awal

Aplikasi tidak membuat kredensial default. Akun lama `admin/admin123` otomatis dinonaktifkan. Buat admin secara interaktif:

```bash
python scripts/manage_users.py create nama_admin --role admin
```

Perintah lain:

```bash
python scripts/manage_users.py list
python scripts/manage_users.py reset-password nama_admin
python scripts/manage_users.py disable nama_pengguna
```

Alternatif bootstrap satu kali dapat menggunakan `BOOTSTRAP_ADMIN_USERNAME` dan `BOOTSTRAP_ADMIN_PASSWORD` (minimal 12 karakter). Hapus kedua variabel setelah admin dibuat.

## Backup dan restore

Backup SQLite otomatis berjalan setiap hari pada `BACKUP_HOUR`, memakai SQLite online backup dan `PRAGMA quick_check`. Retensi dikontrol oleh `BACKUP_RETENTION_DAYS`. Import massal dan restore selalu membuat backup pengaman.

Backup manual:

```bash
python scripts/backup_db.py
```

Restore hanya menerima nama file dari `BACKUP_DIR` dan memerlukan frasa konfirmasi:

```bash
python scripts/restore_db.py ekraf_YYYY-MM-DD_HHMMSS_+0700_manual.db --confirm RESTORE
```

Setelah restore, jalankan pemeriksaan aplikasi dan pastikan audit, pengguna, serta jumlah record sesuai.

## Import

Import hanya menerima XLSX maksimum sesuai konfigurasi. Alur operasionalnya:

1. unggah dan validasi ke staging;
2. tinjau preview, duplikat, dan kesalahan;
3. unduh laporan kesalahan bila diperlukan;
4. commit data valid;
5. admin dapat rollback satu batch tanpa menghapus histori.

## Respons insiden

Gunakan `X-Request-ID` atau field `code` pada respons error untuk mencari detail teknis di `logs/app.log`. Respons API tidak mengandung traceback.
