# Sigap - AI Agent dengan Tools

AI yang bisa **bertindak**, bukan cuma ngomong. Kamu nanya hal yang butuh data nyata (cuaca, hitungan, waktu, kurs), AI sendiri yang mutusin tool mana yang perlu dipanggil, lalu jawab berdasarkan hasilnya. Dibangun dengan Streamlit dan Google Gemini API (function calling).

## Konsep: Function Calling

Ini beda dari SummaRise/Gambarin/Kawan. Sebelumnya, AI cuma menghasilkan teks dari prompt. Di sini, AI bisa **memutuskan untuk memanggil fungsi Python sungguhan** di tengah proses berpikirnya:

1. Kamu nanya: *"Cuaca di Bandung gimana, terus 100 USD itu berapa Rupiah?"*
2. Gemini membaca pertanyaan, menyadari butuh data nyata, lalu **memanggil 2 fungsi**: `get_weather("Bandung")` dan `convert_currency(100, "USD", "IDR")`
3. Fungsi-fungsi itu benar-benar dieksekusi di server (mengambil data asli dari internet)
4. Hasilnya dikembalikan ke Gemini, yang lalu menyusun jawaban akhir dalam Bahasa Indonesia

Semua ini terjadi otomatis lewat fitur **Automatic Function Calling (AFC)** dari SDK `google-genai` -- kamu cukup kasih daftar fungsi Python biasa (dengan docstring & type hint yang jelas), SDK yang urus sisanya.

## Fitur

- 🌤️ **Cek Cuaca** -- kota apa saja di dunia (Open-Meteo, gratis tanpa key)
- 🧮 **Kalkulator** -- hitung ekspresi matematika dengan aman (tanpa `eval()` mentah)
- 🕐 **Cek Waktu** -- zona waktu manapun (`zoneinfo` bawaan Python, tanpa API)
- 💱 **Konversi Mata Uang** -- kurs terkini (Frankfurter API, gratis tanpa key, termasuk IDR)
- 📏 **Konversi Satuan** -- panjang (km/mil/m/ft/cm/inch), berat (kg/lbs), suhu (celsius/fahrenheit)
- 🎲 **Lempar Dadu** -- dadu virtual, atur jumlah sisi & lemparan
- 🎯 **Fakta Acak** -- fakta menarik random, tanpa API
- 💡 **Tombol Saran Pertanyaan** -- contoh pertanyaan siap klik buat yang belum tahu mau nanya apa
- 🧪 **Panel Tes Tools Manual** -- coba tiap tool langsung dari sidebar, tanpa lewat AI
- 🔧 **Transparansi Tools** -- tiap balasan punya expander "Tools yang dipanggil", nampilin fungsi apa yang dieksekusi dan argumennya -- bagus buat belajar cara kerja agent-nya
- 🔒 **Proteksi Password (opsional)**

## Kenapa 100% gratis?

- Gemini API: tier gratis (`gemini-2.5-flash-lite`)
- Open-Meteo (cuaca & geocoding): gratis, tanpa API key sama sekali
- Frankfurter (kurs mata uang): gratis, tanpa API key, tanpa kuota bulanan
- `zoneinfo` (zona waktu): bawaan Python, tidak butuh API/internet

Tidak ada satupun tool di app ini yang butuh kartu kredit atau API key berbayar.

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Isi Secrets

**Lokal:** salin `.streamlit/secrets.toml.example` jadi `.streamlit/secrets.toml`, isi API key Gemini kamu.

**Streamlit Cloud:** Settings → Secrets:
```toml
GEMINI_API_KEY = "key-gemini-kamu"
APP_PASSWORD = "password-kamu"
```
`GEMINI_API_KEY` wajib, `APP_PASSWORD` opsional.

## 3. Jalankan aplikasi

```bash
streamlit run app.py
```

## 4. Cara pakai -- coba tanya ini

- *"Cuaca di Tokyo gimana sekarang?"*
- *"Jam berapa sekarang di New York?"*
- *"500000 IDR itu berapa Dollar?"*
- *"Kalau gajiku 8 juta dipotong 15%, sisa berapa?"*
- *"Cuaca di Jakarta, terus 50 USD ke Euro berapa?"* (memicu 2 tool sekaligus!)

Klik **"🔧 Tools yang dipanggil"** di bawah tiap balasan buat lihat persisnya fungsi apa yang dieksekusi.

## Catatan teknis

- **Model**: `gemini-2.5-flash-lite` -- mendukung function calling dengan baik di tier gratis
- **AFC (Automatic Function Calling)**: SDK otomatis baca docstring & type hint Python buat tahu kapan/bagaimana memanggil tiap tool -- tidak perlu menulis schema JSON manual
- **Kalkulator aman**: memakai modul `ast` Python buat parsing terkontrol, bukan `eval()` langsung yang berisiko
- **Riwayat chat hanya per-sesi** (`st.session_state`) -- proyek ini fokus ke konsep tools, bukan memori permanen (itu sudah dibahas di proyek Kawan)
- Mau nambah tool sendiri? Cukup tulis fungsi Python baru dengan docstring jelas, tambahkan ke list `AVAILABLE_TOOLS` di `app.py`
