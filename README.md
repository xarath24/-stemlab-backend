# STEM LAB — Backend AI (Spleeter)

Backend ini dibuat untuk halaman STEM LAB yang sudah ada di Vercel. Kontrak API sesuai HTML:
- POST `/api/v1/separate?stems=2stems&format=wav` dengan multipart field `file`
- Mode `2stems`: vocals + accompaniment
- Mode `4stems`: vocals + drums + bass + other
- Mode `5stems`: vocals + drums + bass + piano + other
- JSON sukses: `success`, `job_id`, `output_files`, `processing_time`
- Download: GET `/api/v1/separate/{job_id}/download/{filename}`
- Health: GET `/health`; dokumentasi: GET `/docs`

## Deploy lewat Android
1. Unduh ZIP lalu ekstrak di HP.
2. Buat repository GitHub baru bernama `stemlab-backend`.
3. Upload isi folder hasil ekstrak ke root repository. Pastikan `main.py`, `requirements.txt`, dan `Dockerfile` langsung terlihat di halaman utama repo (bukan di subfolder).
4. Di Railway, buka proyek yang berisi service `Index.html`.
5. Buka service `Index.html` → Settings → Source → Connect Repo.
6. Hubungkan repository `stemlab-backend`. Railway akan mendeteksi Dockerfile dan membangun backend.
7. Pertahankan domain `stemsplit.up.railway.app` pada service ini.
8. Tunggu deployment sukses, lalu buka `https://stemsplit.up.railway.app/health`. Respons benar berupa JSON dengan `"status":"healthy"`.

## Penting
- Vercel tetap menjadi tampilan STEM LAB. Mengganti source service Railway hanya mengubah fungsi service Railway menjadi API.
- Jangan hapus repository frontend `xarath24/Index.html`.
- HTML Vercel saat ini sudah memakai `https://stemsplit.up.railway.app`, jadi alamat API tidak perlu diganti jika domain itu tetap melekat pada service backend.
- `/docs` akan menampilkan dokumentasi FastAPI setelah backend aktif.
- Jangan menghapus service/domain sebelum deployment backend berhasil.

## Variables opsional Railway
`MAX_UPLOAD_MB=100`
`JOB_TTL_HOURS=12`
`CORS_ORIGINS=*`

Untuk penggunaan publik, batasi `CORS_ORIGINS` ke domain Vercel milikmu.

## Catatan
Spleeter + TensorFlow berukuran besar dan butuh CPU/RAM. Build pertama dapat lama; model diunduh saat pertama kali dipakai. Paket ini adalah source backend yang siap dicoba deploy, bukan backend yang sudah terpasang di akun Railway. Jika build atau proses gagal karena resource, kirim Build Logs/Deploy Logs.
