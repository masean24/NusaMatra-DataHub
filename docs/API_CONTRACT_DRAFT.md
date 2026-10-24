# NUSA MATRA — STANDALONE DATA HUB API CONTRACT (`/api/v1`)

**Document ID:** `NM-DH-06`  
**Target Platform:** Nusa Matra — Geographic Decision-Support System (WIA 2026)  
**Compatibility:** Dirancang selaras dengan kebutuhan frontend React & 3D Map Engine (`docs/08-API-SPECIFICATION.md`)  

---

## 1. Konvensi Global, Header & Amplop Respons

### 1.1 Base Path & Format
* **Base URL:** `/api/v1`
* **Format Respons:** `application/json; charset=utf-8` (serta `application/geo+json` untuk endpoint batas wilayah).

### 1.2 Kontrol Mode (`DEMO` vs `LIVE`) & Pinning Snapshot
Setiap endpoint mendukung parameter opsional berikut:
* **Query Parameter:** `?mode=demo` atau `?mode=live` (dapat juga dikirim melalui HTTP Header `X-Data-Mode: DEMO | LIVE`).
* **Snapshot Pinning:** `?snapshot_id=2026.10.0-wia-demo` untuk mengunci respons pada versi rilis data tertentu.

### 1.3 Header Respons Standar
* `X-NusaMatra-Snapshot`: ID snapshot yang melayani permintaan (contoh: `2026.10.0-wia-demo`)
* `X-NusaMatra-Mode`: `DEMO` atau `LIVE`
* `X-Data-Fallback`: `NONE` (normal dari DB/Redis) atau `STATIC_DEMO_BUNDLE` (jika *circuit breaker* aktif)
* `Cache-Control`: `public, max-age=3600, stale-while-revalidate=86400`

---

## 2. Endpoint Wilayah Administrasi (Geographic Regions)

### 2.1 `GET /api/v1/regions`
Mengambil daftar seluruh wilayah administrasi (38 Provinsi dan/atau 514 Kabupaten/Kota) beserta kode jembatan lintas-instansi, titik fokus kamera (`anchor_point`), dan kotak pembatas (`bbox`).
* **Query Parameters:**
  * `level`: `kabupaten_kota` (default) | `provinsi` | `all`
  * `parent_id`: Filter 2 digit kode Provinsi (contoh: `32` untuk Jawa Barat)
  * `q`: Pencarian teks berdasarkan nama wilayah atau kode (contoh: `bogor` atau `3201`)
* **Contoh Respons (`200 OK`):**
```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-wia-demo",
    "mode": "DEMO",
    "boundary_version": "BIG-Kepmendagri-300.2.2-2430-2025",
    "total_count": 514
  },
  "data": [
    {
      "region_id": "3201",
      "parent_region_id": "32",
      "province_name": "Jawa Barat",
      "level": "kabupaten",
      "name": "Kabupaten Bogor",
      "short_name": "Bogor",
      "codes": {
        "kemendagri": "32.01",
        "bps": "3201",
        "kemendikdasmen": "020500"
      },
      "island_group": "Jawa",
      "area_km2": 2991.78,
      "anchor_point": { "lng": 106.836412, "lat": -6.551798 },
      "bbox": [106.4012, -6.7891, 107.1345, -6.3012]
    }
  ]
}
```

### 2.2 `GET /api/v1/regions/{region_id}`
Mengambil profil lengkap satu wilayah (contoh: `3201`), mencakup skor komposit per kategori, nilai seluruh indikator beserta peringkat nasionalnya, dan metadata sumber resmi (*provenance*) per indikator.
* **Contoh Respons (`200 OK`):**
```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-wia-demo",
    "mode": "DEMO"
  },
  "data": {
    "region": {
      "region_id": "3201",
      "parent_region_id": "32",
      "province_name": "Jawa Barat",
      "level": "kabupaten",
      "name": "Kabupaten Bogor",
      "codes": { "kemendagri": "32.01", "bps": "3201", "kemendikdasmen": "020500" },
      "area_km2": 2991.78,
      "anchor_point": { "lng": 106.836412, "lat": -6.551798 },
      "bbox": [106.4012, -6.7891, 107.1345, -6.3012]
    },
    "composite_scores": {
      "overall_priority_index": 64.2,
      "disaster_risk": 78.5,
      "socioeconomic": 48.1,
      "education_access": 59.4,
      "healthcare_access": 54.0,
      "infrastructure": 38.2,
      "data_reliability": 96.8
    },
    "indicators": [
      {
        "indicator_id": "soc_poverty_rate",
        "indicator_name": "Persentase Penduduk Miskin (P0)",
        "category": "socioeconomic",
        "raw_value": 7.23,
        "unit": "percent (%)",
        "normalized_score": 34.15,
        "national_percentile": 41.2,
        "national_rank": 302,
        "reference_year": 2025,
        "quality_flag": "VERIFIED",
        "provenance": {
          "dataset_id": "bps_susenas_kemiskinan_2025",
          "agency_code": "BPS",
          "official_url": "https://webapi.bps.go.id/v1/api/"
        }
      }
    ]
  }
}
```

---

## 3. Endpoint Geometri Batas Wilayah (Boundary Delivery)

### 3.1 `GET /api/v1/boundaries/kabupaten`
Menyajikan geometri batas wilayah 514 Kabupaten/Kota yang telah disimplifikasi secara topologis untuk dirender pada peta 3D.
* **Query Parameters:**
  * `format`: `topojson` (default, ukuran ringan $< 1,8\text{ MB}$ gzipped) | `geojson`
  * `resolution`: `low` (default untuk tampilan nasional) | `high` (untuk tampilan *zoom* provinsi/kabupaten)
  * `province_id`: Filter opsional kode provinsi 2 digit (contoh: `32`)
* **Atribut Properti pada Setiap Poligon Fitur:**
```json
{
  "region_id": "3201",
  "parent_region_id": "32",
  "name": "Kabupaten Bogor",
  "kemendagri_code": "32.01",
  "bps_code": "3201",
  "label_lng": 106.836412,
  "label_lat": -6.551798
}
```

### 3.2 `GET /api/v1/boundaries/provinsi`
Menyajikan geometri batas 38 Provinsi dalam format `topojson` atau `geojson`.

---

## 4. Endpoint Katalog & Matriks Nilai Indikator

### 4.1 `GET /api/v1/indicators`
Mengembalikan daftar seluruh indikator yang dikelompokkan menurut 6 kategori utama (`disaster_risk`, `socioeconomic`, `education_access`, `healthcare_access`, `infrastructure`, `data_reliability`), lengkap dengan status ketersediaan (`DIRECT`, `DERIVED`, `UNAVAILABLE`), rumus turunan, statistik nasional, serta tautan dataset sumbernya.

### 4.2 `GET /api/v1/indicators/{indicator_id}/values`
Endpoint berkecepatan tinggi yang mengembalikan nilai satu indikator untuk seluruh 514 Kabupaten/Kota dalam bentuk kamus (`region_id` $\rightarrow$ nilai) agar peta 3D dapat mengganti *layer* ekstrusi dan warna *choropleth* secara instan tanpa memuat ulang poligon geometri.
* **Contoh Respons (`200 OK`):**
```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-wia-demo",
    "mode": "DEMO"
  },
  "data": {
    "indicator": {
      "indicator_id": "dis_multihazard_index",
      "indicator_name": "Indeks Risiko Bencana Indonesia (IRBI) Multi-Bencana",
      "category": "disaster_risk",
      "unit": "score (0-300)",
      "polarity": "negative",
      "availability_status": "DIRECT",
      "reference_year": 2025,
      "stats": {
        "min": 42.1,
        "p25": 112.4,
        "median": 138.6,
        "mean": 139.2,
        "p75": 165.0,
        "max": 248.4
      },
      "provenance": {
        "dataset_id": "bnpb_irbi_2025",
        "agency_code": "BNPB",
        "dataset_title": "Indeks Risiko Bencana Indonesia (IRBI) Tahun 2025",
        "official_portal_url": "https://data.bnpb.go.id/"
      }
    },
    "values_by_region": {
      "1101": { "raw": 168.4, "norm": 76.2, "pct": 78.4, "rank": 111, "flag": "VERIFIED" },
      "1102": { "raw": 145.2, "norm": 58.1, "pct": 54.0, "rank": 236, "flag": "VERIFIED" },
      "3201": { "raw": 172.0, "norm": 79.5, "pct": 82.1, "rank": 92, "flag": "VERIFIED" }
    }
  }
}
```

### 4.3 `POST /api/v1/indicators/composite-query`
Menghitung skor komposit berbobot kustom secara *real-time* untuk mendukung simulasi pengambilan keputusan kebijakan di seluruh 514 Kabupaten/Kota.
* **Contoh Request Body:**
```json
{
  "weights": {
    "dis_multihazard_index": 3500,
    "soc_poverty_rate": 2500,
    "edu_damaged_classrooms_pct": 2000,
    "hlt_stunting_prevalence": 2000
  },
  "filter_province_id": null
}
```

> **v2.2:** weights are integer basis points summing to 10,000. Add `&snapshot=<id>` (or `&snapshot_id=<id>`) to pin an exact immutable snapshot. Check `data.rankable` before rendering rankings; non-rankable scenarios return `regions: []` with `not_rankable_reason`.

---

## 5. Endpoint Provenance Dataset, Snapshot & Kesehatan Sistem

* **`GET /api/v1/datasets`**: Menampilkan daftar seluruh dataset resmi pemerintah yang digunakan beserta URL sumber, lisensi, waktu ingesti terakhir, dan checksum `SHA-256` arsip mentahnya.
* **`GET /api/v1/snapshots`**: Menampilkan daftar versi snapshot data yang tersedia (`DEMO` dan `LIVE`) beserta persentase kelengkapan indikator nasional.
* **`GET /api/v1/health`**: Pemeriksaan kesehatan layanan API, koneksi PostGIS, status cache Redis, dan kesiapan *static fallback bundle*.