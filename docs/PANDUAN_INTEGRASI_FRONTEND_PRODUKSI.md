# 🗺️ Panduan Integrasi Frontend Produksi (v2) — Nusa Matra Data Hub
### *Spesifikasi Endpoint, Kontrak Data, dan Panduan Konsumsi API untuk Peta 3D & Dashboard*

| Parameter | Keterangan |
|---|---|
| **Base URL Produksi** | `https://api.orangkeren.me` |
| **Status API** | ✅ **159/159 Unit & Integration Tests Passing** |
| **Dokumentasi Interaktif (Scalar)** | [https://api.orangkeren.me/docs](https://api.orangkeren.me/docs) |
| **Formal Schema (ReDoc)** | [https://api.orangkeren.me/redoc](https://api.orangkeren.me/redoc) |
| **OpenAPI 3.1 Raw Spec** | [https://api.orangkeren.me/openapi.json](https://api.orangkeren.me/openapi.json) |
| **Runtime Data Modes** | Dual: `mode=demo` (514 wilayah ilustratif) & `mode=live` (data resmi kementerian) |

---

## 📌 Ringkasan Pembaruan untuk Frontend (TL;DR)

0. **Katalog v2.3:** tiga indikator restricted (`meta_dapodik_sync_rate`, `edu_school_travel_time_p90`, `hlt_realtime_icu_occupancy`) tidak lagi ada di katalog publik. Snapshot baru 30 indikator / 29 berdata; snapshot lama 33 / 29 tetap bisa di-pin. Contoh response ada di `docs/staging_samples/retirement/`.
1. **Semantik Skor Kanonik (v2.1):** `score_direction: "higher_is_need"`. Skor dan `normalized_score` bernilai 100 berarti **paling rentan / paling butuh intervensi**, konsisten di DEMO maupun LIVE. Rank 1 = wilayah paling prioritas.
2. **Kebijakan Data Missing (v2.1):** Missing **tidak lagi dihitung nol**. Wilayah dengan cakupan bobot ≥70% dan minimal 2 komponen tetap diranking memakai bobot per wilayah (`effective_weights_region`). Wilayah di bawah ambang masuk `insufficient_data`, bukan ranking.
3. **Rank Nasional + Rank Filter:** `national_rank` selalu posisi se-Indonesia; `rank` adalah posisi di dalam hasil filter provinsi.
4. **Transparansi per Wilayah:** Setiap region menyertakan `coverage_pct`, `components_used`, `missing_indicators`, `effective_weights_region`, dan `quality_flags`.
5. **Preset dengan Availability:** `GET /api/v1/indicators/composite-presets` kini menyertakan `availability` (indikator tersedia, coverage per indikator, bobot efektif, dan `rankable`).
6. **Endpoint Coverage Sekali Panggil (BE-03):** `GET /api/v1/indicators/coverage?mode=live` menyajikan status ketersediaan seluruh indikator.
7. **Peta Batas Wilayah 3D Jauh Lebih Cepat (BE-05):** Header `Cache-Control: public, max-age=604800, immutable` (7 hari) aktif di `/boundaries/*`.
8. **Validasi Mode Ketat (BE-02):** Parameter `mode` strict: `?mode=demo` atau `?mode=live` (huruf kecil).
9. **Snapshot Immutable (v2.2):** resolve snapshot aktif via `GET /api/v1/snapshots?mode=live`; gunakan `snapshot=<id>` (alias) atau `snapshot_id=<id>`. `content_sha256` adalah digest konten kanonik; `manifest_checksum` bukan content hash. Unknown snapshot → 404, tanpa fallback.
10. **Coverage Eksplisit (v2.2):** snapshot baru v2.3: `indicator_completeness_pct` = 29/30 = 96.7; snapshot lama tetap 29/33 = 87.9. `meta.coverage.available` = cakupan wilayah (514), sedangkan hitungan indikator ada di `meta.indicator_coverage`.
11. **Composite Rankability (v2.2):** periksa `data.rankable`. Jika false, `regions` kosong dan `not_rankable_reason` menjelaskan ambang yang gagal; jangan render ranking.
12. **Normalisasi Lanny Jaya (v2.2):** `inf_safe_water_pct` region `9507` sekarang `norm: 78.89` (bukan 100), flag tetap `IMPUTED_PROVINCE` dengan provenance provinsi Papua Pegunungan.

> Handoff lengkap: `docs/FRONTEND_HANDOFF_V2_2.md` · Spesifikasi snapshot: `docs/SNAPSHOT_VERSIONING_V2_2.md` · Root cause: `docs/INTEGRITY_FIX_V2_2.md`.

---

## 1. Dynamic Composite Query & Kebijakan Data Missing (v2.1)

Endpoint `POST /api/v1/indicators/composite-query` digunakan untuk simulasi pembobotan prioritas kebijakan oleh pengambil keputusan secara *real-time*.

### Aturan Input Bobot
- Bobot dikirim dalam satuan **integer basis points** (100% = 10.000 bps; misal 35% = 3500).
- Setiap nilai bobot harus berada di rentang `0` sampai `10000`.
- Total penjumlahan seluruh bobot wajib tepat bernilai **10.000**.
- Tidak boleh mengirim objek bobot kosong `{}` (otomatis ditolak HTTP 422).

### Semantik Skor Kanonik (v2.1)
- `score_direction: "higher_is_need"` — `normalized_score` dan `composite_score` bernilai 100 berarti **paling rentan / paling butuh intervensi**, konsisten di DEMO maupun LIVE.
- Rank 1 = wilayah paling prioritas.
- `national_rank` = posisi se-Indonesia (sebelum filter provinsi).
- `rank` = posisi di dalam hasil filter yang dikembalikan.

### Kebijakan Data Missing (v2.1)
1. **Indikator kosong secara nasional** dikeluarkan dari perhitungan; bobot indikator yang tersisa diskalakan ke 10.000 bps (`renormalized: true`).
2. **Indikator tersedia nasional tetapi kosong di sebagian wilayah**:
   - `coverage_pct` per wilayah = bobot yang memiliki observasi ÷ 10.000 × 100%.
   - Wilayah dengan `coverage_pct >= 70` **dan** minimal 2 komponen tetap diranking. Bobot komponen yang ada diskalakan ulang ke 10.000 bps di `effective_weights_region`.
   - Wilayah di bawah ambang **tidak diranking**; masuk `insufficient_data` beserta komponen yang tersedia dan `reason`.
   - Missing **tidak pernah** dihitung sebagai nol dengan bobot penuh.
3. Ambang dapat diubah melalui `NM_COMPOSITE_MIN_COVERAGE_PCT` (default 70) dan `NM_COMPOSITE_MIN_COMPONENTS` (default 2).

### Contoh Perhitungan (Golden)
Dengan komponen `72.1`, `61.5`, `70.3` dan bobot efektif `43.75%`, `31.25%`, `25%`:

```text
72.1 × 0.4375 = 31.54375
61.5 × 0.3125 = 19.21875
70.3 × 0.2500 = 17.57500
------------------------------
Total         = 68.33750 → 68.34
```

Angka **68.42** pada dokumen v2 sebelumnya salah dan tidak dapat direproduksi dari data mana pun.

### Contoh Request

```typescript
const response = await fetch("https://api.orangkeren.me/api/v1/indicators/composite-query?mode=live", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    weights: {
      soc_poverty_rate: 3000,          // 30%
      hlt_stunting_prevalence: 3000,   // 30%
      inf_safe_water_pct: 2000,        // 20%
      inf_safe_sanitation_pct: 2000    // 20%
    },
    filter_province_id: "33" // Jawa Tengah
  })
});

const result = await response.json();
```

### Contoh Response — wilayah dengan data parsial (LIVE, Jawa Tengah)

```json
{
  "status": "success",
  "meta": {
    "snapshot_id": "2026.10.0-official-live",
    "mode": "LIVE",
    "boundary_version": null,
    "total_count": 35,
    "coverage": null,
    "data_origin": null,
    "last_success_at": null,
    "is_stale": null
  },
  "data": {
    "total_regions": 35,
    "total_eligible_national": 513,
    "total_excluded": 0,
    "score_direction": "higher_is_need",
    "min_coverage_pct": 70,
    "min_components": 2,
    "weights_basis_points": {
      "soc_poverty_rate": 3000,
      "hlt_stunting_prevalence": 3000,
      "inf_safe_water_pct": 2000,
      "inf_safe_sanitation_pct": 2000
    },
    "unavailable_indicators": [],
    "effective_weights": {
      "soc_poverty_rate": 3000,
      "hlt_stunting_prevalence": 3000,
      "inf_safe_water_pct": 2000,
      "inf_safe_sanitation_pct": 2000
    },
    "renormalized": false,
    "regions": [
      {
        "region_id": "3307",
        "region_name": "Kabupaten Wonosobo",
        "composite_score": 35.06,
        "rank": 1,
        "national_rank": 80,
        "coverage_pct": 100.0,
        "components_used": ["hlt_stunting_prevalence", "inf_safe_sanitation_pct", "inf_safe_water_pct", "soc_poverty_rate"],
        "missing_indicators": [],
        "effective_weights_region": {
          "hlt_stunting_prevalence": 3000,
          "inf_safe_sanitation_pct": 2000,
          "inf_safe_water_pct": 2000,
          "soc_poverty_rate": 3000
        },
        "component_scores": {
          "soc_poverty_rate": 28.14,
          "hlt_stunting_prevalence": 56.79,
          "inf_safe_water_pct": 10.06,
          "inf_safe_sanitation_pct": 37.85
        },
        "quality_flags": {
          "hlt_stunting_prevalence": "VERIFIED",
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      },
      {
        "region_id": "3372",
        "region_name": "Kota Surakarta",
        "composite_score": 9.57,
        "rank": 35,
        "national_rank": 487,
        "coverage_pct": 70.0,
        "components_used": ["inf_safe_sanitation_pct", "inf_safe_water_pct", "soc_poverty_rate"],
        "missing_indicators": ["hlt_stunting_prevalence"],
        "effective_weights_region": {
          "inf_safe_sanitation_pct": 2857,
          "inf_safe_water_pct": 2857,
          "soc_poverty_rate": 4286
        },
        "component_scores": {
          "soc_poverty_rate": 14.24,
          "hlt_stunting_prevalence": null,
          "inf_safe_water_pct": 0.0,
          "inf_safe_sanitation_pct": 12.13
        },
        "quality_flags": {
          "inf_safe_sanitation_pct": "VERIFIED",
          "inf_safe_water_pct": "VERIFIED",
          "soc_poverty_rate": "VERIFIED"
        }
      }
    ],
    "insufficient_data": []
  }
}
```

> Surakarta memiliki cakupan 70% (3 dari 4 komponen). Bobotnya didistribusikan ulang ke `4286 + 2857 + 2857 = 10000`; missing **tidak** dihitung nol.

### Contoh Response — wilayah yang dikeluarkan dari ranking (LIVE, Sumatera Utara)

```json
{
  "total_regions": 32,
  "total_eligible_national": 511,
  "total_excluded": 1,
  "unavailable_indicators": ["inf_asphalt_road_village_pct"],
  "effective_weights": {
    "dis_multihazard_index": 4667,
    "dis_flood_hazard_idx": 2000,
    "inf_electrification_pct": 3333
  },
  "renormalized": true,
  "insufficient_data": [
    {
      "region_id": "1277",
      "region_name": "Kota Padangsidimpuan",
      "coverage_pct": 33.3,
      "components_used": ["inf_electrification_pct"],
      "missing_indicators": ["dis_multihazard_index", "dis_flood_hazard_idx", "inf_asphalt_road_village_pct"],
      "component_scores": {
        "dis_multihazard_index": null,
        "dis_flood_hazard_idx": null,
        "inf_asphalt_road_village_pct": null,
        "inf_electrification_pct": 0.9
      },
      "reason": "COVERAGE_BELOW_THRESHOLD"
    }
  ]
}
```

> Padangsidimpuan hanya punya 1 komponen (33,3%). Wilayah ini **tidak** diberi rank dan tidak dapat melonjak ke peringkat 1 seperti pada perilaku lama.

> [!TIP]
> **Rekomendasi UI FE:** Tampilkan badge `coverage_pct` per wilayah dan daftar `missing_indicators`. Tampilkan juga `insufficient_data` sebagai panel "data belum cukup", bukan sebagai ranking bernilai rendah.

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
    "snapshot_id": "2026.10.0-live-<sha16>",
    "mode": "LIVE",
    "total_count": 30,
    "coverage": {
      "available": 29,
      "total_regions": 514,
      "missing_region_ids": [],
      "mode": "LIVE"
    }
  },
  "data": {
    "snapshot_id": "2026.10.0-live-<sha16>",
    "mode": "LIVE",
    "total_indicators": 30,
    "available_indicators_count": 29,
    "empty_indicators_count": 1,
    "empty_indicators": [
      "inf_asphalt_road_village_pct"
    ],
    "indicators": {
      "soc_poverty_rate": {
        "name": "Persentase Penduduk Miskin (P0)",
        "category": "socioeconomic",
        "available": true,
        "coverage_count": 514,
        "coverage_pct": 100.0
      },
      "inf_asphalt_road_village_pct": {
        "name": "Persentase Desa dengan Jalan Utama Aspal/Beton",
        "category": "infrastructure",
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
| 5 | `GET` | `/api/v1/indicators` | Katalog 30 indikator publik (disertai `live_available`) |
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
