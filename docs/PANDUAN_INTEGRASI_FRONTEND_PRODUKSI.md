# 🗺️ Panduan Integrasi Frontend Produksi (v2) — Nusa Matra Data Hub
### *Spesifikasi Endpoint, Kontrak Data, dan Panduan Konsumsi API untuk Peta 3D & Dashboard*

| Parameter | Keterangan |
|---|---|
| **Base URL Produksi** | `https://api.orangkeren.me` |
| **Status API** | ✅ **100% Siap Produksi (81/81 Unit & Integration Tests Passing)** |
| **Dokumentasi Interaktif (Scalar)** | [https://api.orangkeren.me/docs](https://api.orangkeren.me/docs) |
| **Formal Schema (ReDoc)** | [https://api.orangkeren.me/redoc](https://api.orangkeren.me/redoc) |
| **OpenAPI 3.1 Raw Spec** | [https://api.orangkeren.me/openapi.json](https://api.orangkeren.me/openapi.json) |
| **Runtime Data Modes** | Dual: `mode=demo` (514 wilayah ilustratif) & `mode=live` (data resmi kementerian) |

---

## 📌 Ringkasan Pembaruan untuk Frontend (TL;DR)

1. **Composite Query Auto-Renormalization (BE-08):** Bobot query otomatis diskalakan ulang jika ada indikator yang kosong di mode LIVE (`renormalized: true`). Skor prioritas wilayah dijamin **adil dan selalu berada di rentang 0–100**.
2. **Endpoint Coverage Sekali Panggil (BE-03):** Endpoint baru `GET /api/v1/indicators/coverage?mode=live` menyajikan status ketersediaan ke-33 indikator. Frontend bisa langsung menonaktifkan (*gray-out*) layer yang kosong saat aplikasi dibuka.
3. **Peta Batas Wilayah 3D Jauh Lebih Cepat (BE-05):** Header `Cache-Control: public, max-age=604800, immutable` (7 hari) sudah aktif di `/boundaries/*`.
4. **Validasi Mode Ketat (BE-02):** Parameter `mode` sekarang strict: gunakan `?mode=demo` atau `?mode=live` (huruf kecil).

---

## 1. Dynamic Composite Query & Auto-Renormalization (BE-08 & BE-01)

Endpoint `POST /api/v1/indicators/composite-query` digunakan untuk simulasi pembobotan prioritas kebijakan oleh pengambil keputusan secara *real-time*.

### Aturan Input Bobot:
- Bobot dikirim dalam satuan **integer basis points** (100% = 10.000 bps; misal 35% = 3500).
- Setiap nilai bobot harus berada di rentang `0` sampai `10000`.
- Total penjumlahan seluruh bobot wajib tepat bernilai **10.000**.
- Tidak boleh mengirim objek bobot kosong `{}` (otomatis ditolak HTTP 422).

### Mekanisme Fair Renormalization (BE-08):
Di mode LIVE, jika pengguna memilih skenario kebijakan yang memuat indikator yang belum tersedia datanya (misal ruang kelas rusak `edu_damaged_classrooms_pct`):
1. Backend **tidak akan membiarkan skor anjlok separuh**.
2. Bobot indikator yang memiliki data **otomatis diskalakan ulang ke 10.000 bps**.
3. Respons menyertakan informasi provenance:
   - `renormalized: true`
   - `unavailable_indicators: ["edu_damaged_classrooms_pct"]`
   - `effective_weights`: Bobot aktual setelah diskalakan.

### Contoh Request & Response (TypeScript / JavaScript):

```typescript
// Contoh panggilan Composite Query dari Frontend
const response = await fetch("https://api.orangkeren.me/api/v1/indicators/composite-query?mode=live", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    weights: {
      dis_multihazard_index: 3500,     // 35%
      soc_poverty_rate: 2500,          // 25%
      edu_damaged_classrooms_pct: 2000,// 20% (kosong di LIVE)
      hlt_stunting_prevalence: 2000    // 20%
    },
    filter_province_id: "32" // Opsional: filter 2-digit Jawa Barat
  })
});

const result = await response.json();
```

#### Struktur Response:
```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-official-live",
    "mode": "LIVE",
    "total_count": 27
  },
  "data": {
    "total_regions": 27,
    "weights_basis_points": {
      "dis_multihazard_index": 3500,
      "soc_poverty_rate": 2500,
      "edu_damaged_classrooms_pct": 2000,
      "hlt_stunting_prevalence": 2000
    },
    "unavailable_indicators": ["edu_damaged_classrooms_pct"],
    "effective_weights": {
      "dis_multihazard_index": 4375,
      "soc_poverty_rate": 3125,
      "hlt_stunting_prevalence": 2500
    },
    "renormalized": true,
    "regions": [
      {
        "region_id": "3201",
        "region_name": "Kabupaten Bogor",
        "composite_score": 68.42,
        "rank": 1,
        "component_scores": {
          "dis_multihazard_index": 72.1,
          "soc_poverty_rate": 61.5,
          "hlt_stunting_prevalence": 70.3
        }
      }
    ]
  }
}
```

> [!TIP]
> **Rekomendasi UI FE:** Jika `data.renormalized === true`, tampilkan badge kecil atau tooltip: *"1 indikator belum tersedia di mode LIVE; bobot otomatis dinormalisasi ulang ke 100%."*

---

## 2. Deteksi Layer Peta 3D Sekali Panggil (BE-03)

Sebelum merender toggle layer indikator di sidebar peta 3D, frontend dapat memanggil endpoint matriks ketersediaan:

```http
GET https://api.orangkeren.me/api/v1/indicators/coverage?mode=live
```

### Format Response:
```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-official-live",
    "mode": "LIVE",
    "total_count": 33,
    "coverage": {
      "available": 16,
      "total_regions": 514,
      "missing_region_ids": [],
      "mode": "LIVE"
    }
  },
  "data": {
    "snapshot_id": "2026.10.0-official-live",
    "mode": "LIVE",
    "total_indicators": 33,
    "available_indicators_count": 16,
    "empty_indicators_count": 17,
    "empty_indicators": [
      "edu_damaged_classrooms_pct",
      "edu_net_enrollment_sma",
      "..."
    ],
    "indicators": {
      "soc_poverty_rate": {
        "name": "Persentase Penduduk Miskin (P0)",
        "category": "socioeconomic",
        "available": true,
        "coverage_count": 487,
        "coverage_pct": 94.7
      },
      "edu_damaged_classrooms_pct": {
        "name": "Persentase Ruang Kelas Rusak (SD)",
        "category": "education_access",
        "available": false,
        "coverage_count": 0,
        "coverage_pct": 0.0
      }
    }
  }
}
```

### Implementasi di Komponen Layer UI:
```javascript
// Cek ketersediaan layer saat inisialisasi state
const isLayerAvailable = coverageData.indicators[indicatorId]?.available;

<LayerToggle 
  label={indicator.name}
  disabled={!isLayerAvailable}
  tooltip={!isLayerAvailable ? "Data resmi belum dirilis di portal pemerintah" : undefined}
/>
```

---

## 3. Batas Administrasi Geometris 3D (BIG 2026)

Backend menyediakan polygon batas wilayah hasil simplifikasi topologi resmi dari Badan Informasi Geospasial (BIG) 2026:

| Endpoint | Kegunaan di 3D Map | Parameter |
|---|---|---|
| `GET /api/v1/boundaries/kabupaten` | Poligon 514 Kabupaten / Kota | `resolution=low` (default, cepat) / `high` (zoom detail)<br/>`province_id=32` (filter 1 provinsi)<br/>`format=geojson` |
| `GET /api/v1/boundaries/provinsi` | Poligon 38 Provinsi | `resolution=low` / `high`<br/>`format=geojson` |

### Kebijakan Caching:
- Respons menyertakan `Cache-Control: public, max-age=604800, immutable`.
- Browser dan Cloudflare akan meng-cache payload polygon selama **7 hari**. Pengguna yang membuka kembali peta 3D akan merasakan loading instan (*cache hit < 50ms*).
- *Catatan:* Format yang didukung adalah `format=geojson` (default). Permintaan `format=topojson` akan ditolak HTTP 422 karena format native yang dipakai renderer 3D adalah GeoJSON FeatureCollection.

---

## 4. Pemantauan Gempa Bumi Real-Time BMKG

Endpoint gempabumi terhubung langsung ke feed terbuka BMKG dengan in-memory cache TTL 60 detik:

| Endpoint | Deskripsi |
|---|---|
| `GET /api/v1/earthquakes/geojson` | **RFC 7946 GeoJSON FeatureCollection siap render marker/pulsa 3D** |
| `GET /api/v1/earthquakes/latest` | Gempa bumi mutakhir nasional + link Shakemap BMKG |
| `GET /api/v1/earthquakes/recent` | 15 gempa bumi berkekuatan M ≥ 5.0 |
| `GET /api/v1/earthquakes/felt` | 15 gempa bumi dirasakan warga (+ skala intensitas MMI) |
| `GET /api/v1/earthquakes/summary` | Ringkasan statistik gempa 24 jam terakhir |

### Atribut Visual Siap Render pada Setiap Feature:
```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [104.68, -5.40] // [Longitude, Latitude]
  },
  "properties": {
    "magnitude": 5.2,
    "depth_km": 10.0,
    "place": "Pusat gempa berada di laut 84 km BaratDaya Tanggamus",
    "time_iso": "2026-10-22T04:12:00Z",
    "tsunami_risk": "Tidak berpotensi tsunami",
    "visual_radius_px": 28.5,   // Langsung pakai untuk radius point/circle di Mapbox/Deck.gl
    "visual_color": "#f97316",   // Kode warna gradien urgensi gempa
    "severity": "MODERATE"       // LOW | MODERATE | HIGH | SEVERE
  }
}
```

> [!NOTE]  
> Seluruh endpoint gempa bumi menggunakan header `Cache-Control: no-cache, must-revalidate, max-age=0` agar frontend selalu memperoleh pembaharuan kejadian gempa tanpa tertahan cache browser.

---

## 5. Ringkasan Endpoint Produksi

| No | Metode | Path | Keterangan |
| :-: | :---: | :--- | :--- |
| 1 | `GET` | `/` | Service health & daftar URL endpoint |
| 2 | `GET` | `/api/v1/health` | Status database & environment |
| 3 | `GET` | `/api/v1/regions` | Daftar 514 wilayah (filter `level`, `parent_id`, `q`) |
| 4 | `GET` | `/api/v1/regions/{id}` | Detail profil lengkap wilayah & skor indikator |
| 5 | `GET` | `/api/v1/indicators` | Katalog 33 indikator (disertai `live_available`) |
| 6 | `GET` | `/api/v1/indicators/coverage` | **Matriks ketersediaan layer per mode** |
| 7 | `GET` | `/api/v1/indicators/{id}/values` | Matriks nilai indikator 514 wilayah (`values_by_region`) |
| 8 | `POST` | `/api/v1/indicators/composite-query` | **Kalkulasi skor komposit tertimbang (auto-renormalize)** |
| 9 | `GET` | `/api/v1/indicators/composite-presets` | 4 Preset skenario kebijakan resmi WIA 2026 |
| 10 | `GET` | `/api/v1/boundaries/kabupaten` | Polygon 514 Kab/Kota (GeoJSON, cache 7 hari) |
| 11 | `GET` | `/api/v1/boundaries/provinsi` | Polygon 38 Provinsi (GeoJSON, cache 7 hari) |
| 12 | `GET` | `/api/v1/datasets` | Metadata registri dataset kementerian resmi |
| 13 | `GET` | `/api/v1/snapshots` | Versi snapshot data aktif |
| 14 | `GET` | `/api/v1/earthquakes/geojson` | **Feed GeoJSON seismik BMKG siap render 3D** |
| 15 | `GET` | `/api/v1/earthquakes/latest` | Gempa terbaru BMKG + Shakemap |
| 16 | `GET` | `/api/v1/earthquakes/recent` | 15 Gempa M ≥ 5.0 |
| 17 | `GET` | `/api/v1/earthquakes/felt` | 15 Gempa dirasakan |
| 18 | `GET` | `/api/v1/earthquakes/summary` | Analitik seismik nasional |

---

*Dokumen ini diterbitkan untuk keselarasan pengembangan modul Peta 3D & Digital Twin Nusa Matra (WIA 2026).*
