<div align="center">

# 🗺️ Nusa Matra Data Hub
### *National Geographic Decision-Support Engine & Unified Data Hub (WIA 2026)*

Backend API geospasial terintegrasi penyedia data 33 indikator pembangunan, kebencanaan, infrastruktur, dan pemantauan gempa bumi *real-time* BMKG untuk 514 Kabupaten/Kota dan 38 Provinsi di Indonesia.

[![Production Status](https://img.shields.io/badge/Production-LIVE%20at%20api.orangkeren.me-success?style=for-the-badge&logo=cloudflare&logoColor=white)](https://api.orangkeren.me)
[![Tests](https://img.shields.io/badge/Tests-81%2F81%20Passing%20(100%25)-brightgreen.svg?style=for-the-badge&logo=pytest&logoColor=white)](tests/)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2.10-E92063.svg?style=flat&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![Database](https://img.shields.io/badge/Database-aiosqlite%20%7C%20Dual%20DEMO%2FLIVE-003B57.svg?style=flat&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![BMKG Live](https://img.shields.io/badge/Realtime-BMKG%20Earthquakes-orange.svg?style=flat&logo=rss&logoColor=white)](https://data.bmkg.go.id)
[![Documentation](https://img.shields.io/badge/API%20Docs-Scalar%20%26%20ReDoc-blue.svg?style=flat&logo=openapiinitiative&logoColor=white)](https://api.orangkeren.me/docs)

---

[🚀 Status Produksi](#-status-produksi--deployment) •
[📌 Ringkasan Eksekutif](#-ringkasan-eksekutif) •
[🏛️ Sumber Data Pemerintah](#-katalog-sumber-data-pemerintah-6-instansi) •
[🌋 Integrasi Real-Time BMKG](#-integrasi-pemantauan-gempa-bumi-real-time-bmkg) •
[⚙️ Keunggulan Teknis](#-keunggulan-teknis--engineering-excellence) •
[🧪 Panduan Uji Coba Cepat](#-panduan-uji-coba-cepat-dewan-juri) •
[📖 Dokumentasi Interaktif](#-dokumentasi-interaktif-api)

---

</div>

## 🚀 Status Produksi & Deployment

Nusa Matra Data Hub telah **aktif secara live di production** dengan SSL terenkripsi, CDN caching, dan dual runtime environment (DEMO & Official LIVE):

- 🌐 **Base Production URL:** [`https://api.orangkeren.me`](https://api.orangkeren.me)
- 🌟 **Interactive Scalar API Reference:** [`https://api.orangkeren.me/docs`](https://api.orangkeren.me/docs) *(atau [`/scalar`](https://api.orangkeren.me/scalar))*
- 📖 **Formal ReDoc Schema View:** [`https://api.orangkeren.me/redoc`](https://api.orangkeren.me/redoc)
- 📄 **OpenAPI 3.1 JSON Specification:** [`https://api.orangkeren.me/openapi.json`](https://api.orangkeren.me/openapi.json)

---

## 📌 Ringkasan Eksekutif

Dalam perencanaan pembangunan dan mitigasi kebencanaan nasional, pengambil kebijakan kerap terhambat oleh **fragmentasi data (*data silos*)**: data kemiskinan berada di BPS, risiko bencana di BNPB, fasilitas pendidikan di Kemendikdasmen, prevalensi stunting di Kemenkes, batas peta wilayah di BIG/Kemendagri, dan peringatan gempa di BMKG. Sistem pengkodean wilayah antar-instansi pun kerap berbeda (kode titik Kemendagri `32.01` vs kode numerik BPS `3201`).

**Nusa Matra Data Hub** hadir sebagai **lapisan agregasi data dan mesin pendukung keputusan geospasial (*decision-support backend engine*)** yang:
1. **Menyelaraskan Kode Wilayah (*Cross-Agency Code Bridging*)** untuk 514 Kabupaten/Kota dan 38 Provinsi (termasuk 4 provinsi baru Papua).
2. **Menyajikan 33 Indikator Pembangunan Strategis** dalam format kamus ringkas `values_by_region` (*sub-10ms response time*) yang siap diekstrusi instan oleh peta 3D frontend.
3. **Dynamic Composite Query Engine berbasis Integer Basis-Points (10.000 bps = 100%)** dengan **Automatic Fair Renormalization** untuk simulasi bobot prioritas kebijakan tanpa distorsi matematika.
4. **Pemantauan Gempa Bumi *Real-Time* BMKG** dengan output GeoJSON (RFC 7946) lengkap dengan radius visual 3D, kedalaman hiposenter, dan status potensi tsunami.
5. **Dual Architecture (DEMO vs LIVE Mode)** dengan prinsip integritas tinggi (*Fail-Closed Architecture*).

---

## 🏛️ Katalog Sumber Data Pemerintah (6 Instansi)

Backend mengintegrasikan data terverifikasi dari 6 kementerian dan lembaga resmi Republik Indonesia:

| Instansi | Jenis Data Terintegrasi | Cakupan Wilayah | Status di Hub |
|---|---|---|---|
| **Badan Informasi Geospasial (BIG)** | Batas administrasi resmi polygon 2026 (Kepmendagri No. 300.2.2-2430) | 514 Kab/Kota & 38 Provinsi | ✅ Low & High Resolution GeoJSON |
| **Badan Pusat Statistik (BPS)** | 11 indikator sosial-ekonomi + 3 indikator infrastruktur SDGs | 514 Kab/Kota | ✅ WebAPI Resmi (Live Ingested) |
| **BNPB (InaRISK / IRBI 2024)** | Indeks Risiko Bencana Indonesia multi-hazard & spesifik | 514 Kab/Kota | ✅ IRBI 2024 Terbitan Resmi |
| **Kementerian Kesehatan (Kemenkes)** | Prevalensi stunting balita (Survei Kesehatan Indonesia 2023) | 507 Kab/Kota | ✅ SKI 2023 Resmi |
| **Kemendikdasmen** | Jumlah sekolah & peserta didik (SD, SMP, SMA, SMK, SLB) | 514 Kab/Kota | ✅ Data Pokok Pendidikan 2026 |
| **BMKG** | Feed kejadian gempa bumi terkini, M ≥ 5.0, dan gempa dirasakan | Nasional Real-Time | ✅ Auto-Feed dengan Cache TTL 60s |

---

## 🌋 Integrasi Pemantauan Gempa Bumi Real-Time BMKG

Nusa Matra menyediakan 5 endpoint khusus pemantauan seismik nasional dari feed terbuka BMKG (`data.bmkg.go.id`):

- `GET /api/v1/earthquakes/latest` — Informasi gempa bumi paling mutakhir dipublikasikan BMKG.
- `GET /api/v1/earthquakes/recent` — 15 kejadian gempa bumi berkekuatan M ≥ 5.0.
- `GET /api/v1/earthquakes/felt` — 15 kejadian gempa bumi yang dirasakan masyarakat (disertai skala intensitas MMI).
- `GET /api/v1/earthquakes/geojson` — Fitur GeoJSON Point standar (RFC 7946) hasil *deduplication* yang diperkaya atribut visual 3D:
  - `visual_radius_px`: Ukuran radius dinamis berdasarkan magnitudo.
  - `visual_color`: Kode warna hex gradien urgensi (`#ef4444`, `#f97316`, `#eab308`, `#3b82f6`).
  - `depth_km`, `tsunami_risk`, `felt_mmi`, `shakemap_url`.
- `GET /api/v1/earthquakes/summary` — Ringkasan analitik seismik nasional dan status cache upstream.

> [!TIP]
> **Kebijakan Caching & Fail-Closed Upstream:**  
> Endpoint gempa menggunakan in-memory cache dengan TTL 60 detik (`Cache-Control: no-cache, must-revalidate, max-age=0`). Jika server BMKG mengalami gangguan saat request `mode=live`, endpoint bersikap **fail-closed** (HTTP 503) dengan penanda `data_origin`, bukan menyamarkan data simulasi sebagai gempa resmi.

---

## ⚙️ Keunggulan Teknis & Engineering Excellence

### 1. Integer Basis Points & Fair Renormalization (BE-01 & BE-08)
Perhitungan skor komposit multivariat menggunakan integer **basis points (bps)** ($10.000\text{ bps} = 100\%$):
$$\text{Composite Score} = \sum_{i=1}^{n} \left( \text{Normalized Score}_i \times \frac{\text{Effective Weight}_i}{10000} \right)$$
- Menolak bobot negatif, bobot kosong `{}`, dan bobot melebihi batas (HTTP 422).
- **Automatic Fair Renormalization:** Jika suatu indikator belum tersedia pada snapshot aktif (misal di mode LIVE), backend secara otomatis menormalisasi ulang bobot yang tersisa menjadi 10.000 bps dan menandai respons dengan `renormalized: true`, sehingga skor prioritas tetap adil pada rentang 0–100.

### 2. Transparansi Cakupan Data (BE-03)
- Setiap endpoint nilai menyertakan blok `meta.coverage` lengkap dengan jumlah wilayah yang memiliki data, total 514 wilayah, dan daftar `missing_region_ids`.
- Endpoint `GET /api/v1/indicators/coverage` menyajikan status ketersediaan ke-33 indikator dalam satu panggilan ringan agar klien peta 3D dapat menonaktifkan layer yang kosong tanpa query berulang.

### 3. Standarisasi Skema Amplop Respons
Semua respons terstruktur konsisten dengan generic envelope `ApiResponse[T]`:
```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-official-live",
    "mode": "LIVE",
    "boundary_version": "BIG-Kepmendagri-300.2.2-2430-2025",
    "total_count": 514,
    "coverage": {
      "available": 487,
      "total_regions": 514,
      "missing_region_ids": [],
      "mode": "LIVE"
    }
  },
  "data": { ... }
}
```

---

## 🧪 Panduan Uji Coba Cepat (Live Production cURL)

Anda dapat menguji langsung API production di `https://api.orangkeren.me` tanpa instalasi lokal:

### 1. Mengambil Feed GeoJSON Gempa BMKG Siap Render 3D
```bash
curl -s "https://api.orangkeren.me/api/v1/earthquakes/geojson" | head -c 500
```

### 2. Simulasi Formula Prioritas Kebijakan (*Dynamic Composite Query*)
Menghitung prioritas wilayah (Bencana 35% + Kemiskinan 25% + Ruang Rusak 20% + Stunting 20% = 10.000 bps):
```bash
curl -X POST "https://api.orangkeren.me/api/v1/indicators/composite-query?mode=live" \
     -H "Content-Type: application/json" \
     -d '{
       "weights": {
         "dis_multihazard_index": 3500,
         "soc_poverty_rate": 2500,
         "edu_damaged_classrooms_pct": 2000,
         "hlt_stunting_prevalence": 2000
       }
     }'
```

### 3. Cek Ketersediaan Indikator (Coverage Matrix)
```bash
curl -s "https://api.orangkeren.me/api/v1/indicators/coverage?mode=live"
```

### 4. Menjalankan Pengujian Lokal
```powershell
# Clone dan buka repository
cd d:\wia2

# Install dependensi
pip install -r requirements.txt

# Jalankan 81 unit tests
python -m pytest -v
```
*(Hasil: **81 passed** dalam ~18-20 detik).*

---

## 📖 Dokumentasi Interaktif API

- **🌟 Scalar Interactive Reference:** [https://api.orangkeren.me/docs](https://api.orangkeren.me/docs)
  - Layout 3-kolom modern dengan live request playground, syntax highlighter, dan contoh kode multi-bahasa (cURL, Python, JS, dll).
- **📖 ReDoc Formal Schema:** [https://api.orangkeren.me/redoc](https://api.orangkeren.me/redoc)
- **📄 Raw OpenAPI Specification:** [https://api.orangkeren.me/openapi.json](https://api.orangkeren.me/openapi.json)

---

<div align="center">

**Nusa Matra Data Hub — Wilayah Indonesia (WIA) 2026**  
*Membangun Fondasi Pengambilan Keputusan Geospasial yang Terukur, Transparan, dan Tepercaya untuk Indonesia.*

</div>
