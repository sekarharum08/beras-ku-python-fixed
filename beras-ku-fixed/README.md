# BerasKu MVP (Flask + SQLite)

## Menjalankan di Windows
1. Ekstrak ZIP, lalu buka folder `beras-ku-fixed` di VS Code.
2. Buka terminal pada folder tersebut.
3. Jalankan:
   ```bat
   python -m venv venv
   venv\Scripts\activate
   python -m pip install -r requirements.txt
   python app.py
   ```
4. Buka `http://127.0.0.1:5000`.
5. Admin: `http://127.0.0.1:5000/admin` — username `admin`, password `admin123`.

Database `beras_ku.db` dibuat otomatis saat aplikasi pertama dijalankan.

## Pembayaran
Checkout menyediakan COD, Transfer Bank, dan QRIS. Informasi rekening pada kode adalah **contoh** dan harus diganti dengan rekening toko yang benar. Untuk QRIS, letakkan gambar QRIS resmi toko di `static/qris.jpeg`. Aplikasi ini belum memverifikasi pembayaran otomatis atau terhubung ke payment gateway.

Aplikasi ini untuk prototipe/demo. Sebelum dipakai publik, ganti secret key dan kredensial admin serta tambahkan keamanan produksi.
