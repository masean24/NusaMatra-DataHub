# 🗺️ Nusa Matra Data Hub — Backend API

Backend service untuk **Nusa Matra** — Geographic Decision-Support System (WIA 2026), dibangun dengan **FastAPI**, **aiosqlite**, dan **Pydantic v2**.

---

## 🚀 Fitur Utama

- **Katalog 33 Indikator Pembangunan:** Sesuai `INDICATOR_MAPPING.csv` di 6 kategori strategis:
  - `disaster_risk` (IRBI, bahaya banjir/gempa/longsor, frekuensi kejadian, dampak)
  - `socioeconomic` (kemiskinan P0/P2, IPM/HDI, pengeluaran per kapita, pengangguran TPT, dependency ratio)
  - `education_access` (RLS, HLS, APM SMP/SMA, rasio murid-guru SD, kelas rusak)
  - `healthcare_access` (UHH, stunting SKI/SSGI, rasio faskes/dokter, JKN)
  - `infrastructure` (air minum, sanitasi, listrik, internet, jalan aspal/beton)
  - `data_reliability` (kelengkapan data, freshness lag, sinkronisasi Dapodik)
- **Cakupan Spasial Lengkap:** 38 Provinsi dan 514 Kabupaten/Kota dengan kode jembatan lintas-instansi (BPS, Kemendagri, Kemendikdasmen).
- **Fast Values Matrix:** Endpoint `GET /indicators/{id}/values` dalam bentuk format kamus berkecepatan tinggi (`region_id` -> value) untuk ekstrusi 3D dan pewarnaan choropleth instan.
- **Dynamic Composite Query:** `POST /indicators/composite-query` menghitung indeks prioritas tertimbang secara *real-time* berbasis **integer basis points** (sum = 10.000).
- **Boundary Delivery:** GeoJSON FeatureCollection (default) untuk 514 Kabupaten/Kota dan 38 Provinsi.
- **Arsitektur Fail-Closed:** Permintaan mode `LIVE` tidak pernah jatuh (*fallback*) ke simulasi `DEMO` secara diam-diam (HTTP 503 jika sumber LIVE belum terhubung).

---

## 🛠️ Keputusan Desain & Perbaikan Blocker (`REVIEW_AND_BLOCKERS.md`)

| Blocker | Masalah Asal | Solusi Implementasi |
|---|---|---|
| **#1 (CRITICAL)** | LIVE fallback ke DEMO | **Fail-closed**: Endpoint mode `LIVE` merespons HTTP `503 Service Unavailable` dengan header `X-Data-Fallback: UNAVAILABLE`. |
| **#2 (CRITICAL)** | Klaim verifikasi sumber belum lengkap | Semua data fixture lokal diberi flag `DEMO_EXAMPLE`. Tidak ada data sintetis yang diklaim `VERIFIED`. |
| **#3 (CRITICAL)** | Batas kelas IRBI 2025 di CSV tidak akurat | Catatan sumber dipertahankan tanpa perubahan, ambang batas resmi dicatat pada dokumentasi. |
| **#4 (HIGH)** | Format bobot pecahan vs basis points | Menggunakan **integer basis points** (jumlah harus tepat 10.000 basis points / 100%) dengan validasi Pydantic. |
| **#6 (HIGH)** | Primary Key `fact_indicator_values` tanpa tahun | Kolom `reference_year` disertakan dalam Composite Primary Key: `(snapshot_id, region_id, indicator_id, reference_year)`. |
| **#8 (HIGH)** | TopoJSON vs GeoJSON | Endpoint `/boundaries/*` menyajikan **GeoJSON** secara bawaan (`?format=geojson`) agar langsung kompatibel dengan engine peta 3D. |
| **#9 (MEDIUM)** | Label contoh fixture | Flag data `DEMO_EXAMPLE` dipasang pada seluruh 15.934 baris fakta. |

---

## 📦 Menjalankan Secara Lokal

### 1. Prasyarat & Instalasi
Pastikan Python 3.11+ terpasang:
```bash
pip install -r requirements.txt
```

### 2. Pemuatan Database DEMO (Seeding)
Jalankan script seeder untuk menghasilkan SQLite database deterministik:
```bash
python data/seed_db.py
```
*Output memvalidasi: 38 provinsi, 514 kab/kota, 33 metadata indikator, dan 15.934 baris data fakta.*

### 3. Menjalankan Server API
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Akses dokumentasi interaktif OpenAPI Swagger UI:
- **Swagger UI:** [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)
- **ReDoc:** [http://127.0.0.1:8000/api/v1/redoc](http://127.0.0.1:8000/api/v1/redoc)
- **OpenAPI Schema:** [http://127.0.0.1:8000/api/v1/openapi.json](http://127.0.0.1:8000/api/v1/openapi.json)

### 4. Menjalankan Rangkaian Pengujian (Automated Tests)
```bash
python -m pytest -v
```

---

## 🌐 Ringkasan Endpoint API (`/api/v1`)

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/` | Root info layanan, status mode, dan daftar link |
| `GET` | `/api/v1/health` | Pemeriksaan kesehatan sistem, koneksi DB, dan status snapshot |
| `GET` | `/api/v1/regions` | Daftar wilayah administrasi (filter `level`, `parent_id`, `q`) |
| `GET` | `/api/v1/regions/{region_id}` | Profil komprehensif wilayah + skor komposit per domain + seluruh indikator |
| `GET` | `/api/v1/boundaries/kabupaten` | Geometri batas 514 Kab/Kota (`?format=geojson`, `?province_id=32`) |
| `GET` | `/api/v1/boundaries/provinsi` | Geometri batas 38 Provinsi |
| `GET` | `/api/v1/indicators` | Katalog seluruh indikator dikelompokkan menurut 6 kategori utama |
| `GET` | `/api/v1/indicators/{id}/values` | Matriks nilai instan satu indikator untuk seluruh 514 Kab/Kota |
| `POST` | `/api/v1/indicators/composite-query` | Kalkulasi komposit terbobot kustom (*basis points sum = 10000*) |
| `GET` | `/api/v1/datasets` | Registri katalog dataset pemerintah beserta *provenance* dan URL resmi |
| `GET` | `/api/v1/snapshots` | Riwayat versi snapshot dan metrik kelengkapan indikator |
