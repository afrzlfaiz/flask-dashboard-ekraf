# Operasional Keamanan P0

## Konfigurasi production

Production wajib menyediakan `DATABASE_URL`, `SECRET_KEY`, dan `ALLOWED_ORIGINS` melalui environment. Gunakan HTTPS dan set:

```env
FLASK_ENV=production
FLASK_DEBUG=false
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax
```

Aplikasi menolak startup jika URL PostgreSQL tidak tersedia, atau jika konfigurasi production tidak aman.

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

## Database

Database utama berada di Supabase. Atur backup, point-in-time recovery, dan retensi melalui pengaturan proyek Supabase sesuai paket yang digunakan.

## Import

Import hanya menerima XLSX maksimum sesuai konfigurasi. Alur operasionalnya:

1. unggah dan validasi ke staging;
2. tinjau preview, duplikat, dan kesalahan;
3. unduh laporan kesalahan bila diperlukan;
4. commit data valid;
5. admin dapat rollback satu batch tanpa menghapus histori.

## Respons insiden

Gunakan `X-Request-ID` atau field `code` pada respons error untuk mencari detail teknis di `logs/app.log`. Respons API tidak mengandung traceback.
