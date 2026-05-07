# Inventory & Finance Tracker

Aplikasi **Inventory & Finance Tracker** adalah sistem berbasis web yang dirancang untuk membantu entitas bisnis atau perorangan dalam mengelola inventaris barang sekaligus mendata laporan keuangan yang berhubungan dengan transaksi barang tersebut (pemasukan, pengeluaran, profit).

## 🚀 Teknologi yang Digunakan (Tech Stack)

Aplikasi ini menggunakan teknologi berikut untuk sisi Backend (Server) dan Frontend (Klien):

**Backend:**
- **[Flask (Python)](https://flask.palletsprojects.com/)**: Framework web mikro untuk membangun API dan merender tampilan.
- **[MongoDB](https://www.mongodb.com/)**: Database NoSQL yang digunakan untuk menyimpan data barang dan transaksi.
- **Flask-JWT-Extended**: Untuk proses autentikasi.
- **Pandas & Openpyxl**: Untuk pengolahan data (ekspor/impor Excel/CSV).

**Frontend:**
- **[Tailwind CSS](https://tailwindcss.com/)**: Framework CSS utility-first untuk styling.
- **[Alpine.js](https://alpinejs.dev/)**: Framework JavaScript minimalis untuk mengelola state di DOM.
- **[Chart.js](https://www.chartjs.org/)**: Library untuk membuat visualisasi data/grafik interaktif (contoh: di Dashboard).

---

## 🏗️ Struktur Proyek (Panduan untuk Kontributor)

Agar memudahkan bagi siapa pun yang ingin membaca kode atau berkontribusi, berikut adalah peta struktur proyek ini:

```
inventory-finance-tracker/
├── app/                      # Kode utama aplikasi Backend (Python/Flask)
│   ├── models/               # Logika database, query ke MongoDB
│   ├── routes/               # Definisi Endpoint API dan URL aplikasi
│   │   ├── auth.py           # Endpoint Sistem Login & Register
│   │   ├── data.py           # Endpoint API manajemen data
│   │   └── ui.py             # Endpoint untuk me-render HTML (halaman web)
│   ├── services/             # Logika bisnis tambahan
│   ├── config.py             # Konfigurasi aplikasi
│   └── extensions.py         # Koneksi database dan ekstensi Flask lainnya
├── static/                   # Aset yang di-serve secara publik
│   ├── css/                  # Berkas CSS (Input dari Tailwind & Output)
│   └── js/                   # Berkas skrip JS Client-side (mis. dashboard)
├── templates/                # File HTML (Jinja2) untuk UI Frontend
├── tests/                    # File pengujian (unit/integrasi tes)
├── Dockerfile                # Konfigurasi jika ingin menjalankan via Docker
├── package.json              # Daftar library Node.js (untuk Tailwind CSS)
├── requirements.txt          # Daftar library Python
└── run.py                    # Titik masuk utama untuk menjalankan server Flask
```

---

## 🛠️ Cara Menjalankan Proyek di Lokal

Jika kamu ingin menjalankan atau ikut berkontribusi dalam mengembangkan aplikasi ini, ikuti langkah-langkah di bawah ini:

### Prasyarat
- **Python** (versi 3.9 atau lebih baru)
- **Node.js & npm** (terbaru, diperlukan hanya untuk build CSS Tailwind)
- Klaster **MongoDB** (Lokal atau MongoDB Atlas)

### Langkah 1: Setup Frontend (Tailwind CSS)
1. Buka terminal di direktori proyek ini.
2. Install dependency Node:
   ```bash
   npm install
   ```
3. Bangun ulang file CSS Tailwind:
   ```bash
   npm run build
   ```
   *Tip: Saat sedang menyunting HTML/CSS, gunakan `npm run dev` agar CSS langsung terkompilasi saat ada perubahan (watch mode).*

### Langkah 2: Setup Backend (Python Flask)
1. Disarankan untuk menggunakan Virtual Environment:
   ```bash
   python -m venv venv
   source venv/bin/activate       # Di Linux/Mac
   venv\Scripts\activate          # Di Windows
   ```
2. Install library Python:
   ```bash
   pip install -r requirements.txt
   ```
3. Buat file `.env` di direktori terluar (sejajar dengan `run.py`) lalu masukkan variabel wajib (contoh):
   ```
   MONGO_URI="mongodb+srv://<username>:<password>@cluster0.mongodb.net/?retryWrites=true&w=majority"
   SECRET_KEY="rahasia_untuk_sesi_flask"
   JWT_SECRET_KEY="rahasia_untuk_token_apikamu"
   ```
4. Jalankan aplikasi Flask:
   ```bash
   python run.py
   ```
5. Buka browser dan akses ke `http://127.0.0.1:5000` (atau port yang tertera pada terminal).

---

## 🤝 Cara Berkontribusi

Bagi kamu yang tidak mau pusing dan ingin cepat berkontribusi:
1. Pahami struktur folder utama di bagian **Struktur Proyek**.
2. Jika ingin memperbaiki tampilan, cek folder `templates/` (HTML) dan `static/` (CSS/JS).
3. Jika ingin mengubah alur logika data atau menambah API, cek folder `app/routes/`.
4. Jika logika database yang perlu diperbaiki, lihat `app/models/`.
5. **Flow Git**:
   - Lakukan `Fork` pada repositori ini.
   - Buat *branch* baru (contoh: `git checkout -b fitur-tambah-kategori`).
   - Lakukan `Commit` (contoh: `git commit -m "Menambahkan fitur kategori inventaris"`).
   - Lakukan `Push` ke branch tersebut.
   - Ajukan *Pull Request* (PR) kepada kami.
