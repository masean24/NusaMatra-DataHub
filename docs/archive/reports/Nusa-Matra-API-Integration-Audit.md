# Nusa Matra Data Hub — Audit OpenAPI & Handoff Integrasi

**Sumber:** `openapi.json` yang diekspor dari Nusa Matra Data Hub v0.1.0 (diunggah pengguna).  
**Jenis pemeriksaan:** Audit dokumen OpenAPI statis, **bukan** bukti respons API live, isi database, atau hasil test suite.

## Ringkasan

- `openapi`: `3.1.0`; `info.version`: `0.1.0`; deskripsi menyebut mode saat ini `DEMO`.
- 11 operasi API: 10 di bawah `/api/v1`, 1 `GET /`.
- Tujuh schema komponen; seluruh `$ref` ke `#/components/schemas/...` berhasil ditemukan.
- Request `POST /api/v1/indicators/composite-query` menerima `weights: Record<string, integer>` serta `filter_province_id?: string|null`.
- Seluruh endpoint kecuali health dan root merespons dengan envelope `ApiResponse`: `{status, meta, data}`. Namun tipe `data` **tidak ditentukan** dalam schema.

## Daftar operasi yang terdokumentasi

| Method | Path | Tercakup dalam OpenAPI |
|---|---|---|
| GET | `/api/v1/health` | `HealthResponse` |
| GET | `/api/v1/regions` | level, parent_id, q |
| GET | `/api/v1/regions/{region_id}` | profil wilayah |
| GET | `/api/v1/indicators` | katalog indikator |
| GET | `/api/v1/indicators/{indicator_id}/values` | nilai indikator |
| POST | `/api/v1/indicators/composite-query` | integer basis points |
| GET | `/api/v1/boundaries/kabupaten` | format, resolution, province_id |
| GET | `/api/v1/boundaries/provinsi` | format |
| GET | `/api/v1/datasets` | registri dataset |
| GET | `/api/v1/snapshots` | snapshot |
| GET | `/` | informasi root |

## Blocker integrasi

### P0 — Geometry masih placeholder

Deskripsi operasi `/api/v1/boundaries/kabupaten` secara eksplisit berbunyi: "MVP DEMO returns placeholder features without actual polygon geometry." Dokumentasi `/api/v1/boundaries/provinsi` juga menyebut placeholder. Ini belum cukup untuk menampilkan 514 batas kabupaten/kota pada renderer 3D. Endpoint mempunyai opsi `format=geojson` sebagai default tetapi hal ini **tidak menjamin** isi geometri valid.

**Tindakan backend:** pisahkan secara tegas status `geometry_available`, `source`, `boundary_version` dan `data_mode`; sajikan dataset yang memiliki Polygon/MultiPolygon dengan koordinat `[longitude, latitude]` setelah sumber, lisensi, kode, dan versi diverifikasi. Jangan isi poligon acak atau mengklaim ilustrasi sebagai batas resmi.

**Tindakan frontend:** sementara gunakan `HeroDiorama` ilustratif khusus Landing dan fallback DEMO yang jelas di Explore. Jangan meneruskan placeholder ke `validateAndAdaptGeography()` sebagai LIVE.

### P0 — Schema `ApiResponse.data` tidak bertipe

`components.schemas.ApiResponse.properties.data` hanya berisi `{ "title": "Data" }`. Ini membuat tipe spesifik untuk responses wilayah, indikator, nilai, composite, dan geometri tidak dapat digenerate secara aman dari OpenAPI.

**Tindakan backend:** gunakan generic `ApiResponse[T]` dengan Pydantic response models nyata untuk masing-masing route; ekspor ulang OpenAPI, pastikan schema respons menunjuk pada models typed dengan properti dan enum relevan. Untuk geometri, dokumentasikan apakah FeatureCollection menjadi isi `data` atau body response langsung, dan pertahankan satu bentuk yang konsisten.

### P1 — LIVE fail-closed belum dideskripsikan sebagai kontrak

Spesifikasi ini tidak memiliki parameter `mode` atau `snapshot_id` yang ditetapkan pada tiap operasi, dan tidak mendefinisikan respons status `503` di dalam OpenAPI. Kemungkinan mode diatur melalui middleware/header; ketiadaan deklarasi **bukan bukti implementasinya tidak ada**.

**Tindakan backend:** dokumentasikan `X-Data-Mode`, `X-Data-Fallback`, `X-NusaMatra-Mode`, `X-NusaMatra-Snapshot`, `?mode`, dan `?snapshot_id` jika didukung; tambahkan model respons 503 yang eksplisit, lalu uji HTTP request `LIVE` dengan ekspektasi HTTP 503 dan **tanpa** payload DEMO. Jangan mengubah prinsip fail-closed.

### P1 — Adapter GeoJSON ke kontrak engine 3D diperlukan

Engine peta Gemini mengharapkan `GeographyDataset` berupa `FeatureCollection` dengan `metadata` (`datasetId`, `boundaryEditionId`, `codeSystem`, `dataMode`, `isAuthoritative`, `provenanceNote`) dan feature properties `regionId`, `displayName`, `regionCode` yang terstandar. Draft endpoint backend memakai envelope API dan pada dokumen riset properti snake_case seperti `region_id`/`name`.

**Tindakan frontend:** buat adapter `apiBoundaryToGeographyDataset()` yang memvalidasi body sebelum mengubah nama field dan menambahkan metadata berasal dari respons atau registri provenance nyata. Tolak LIVE jika sumber atau versi batas tidak terverifikasi, jangan mengisi `isAuthoritative: true` hanya untuk melewati validator.

### P1 — Batasan komposit diimplementasikan di kode, tetapi belum diekspresikan penuh dalam schema

`weights` bertipe objek nilai integer, dengan ketentuan jumlah 10.000 basis points dalam description. Namun OpenAPI tidak dapat menunjukkan validasi jumlah tepat 10.000 dari schema saat ini. Ekspektasi harus diuji melalui HTTP dengan bobot tepat 10.000, kurang dari 10.000, lebih dari 10.000, desimal, serta indicator_id yang tidak dikenal.

## Smoke tests yang perlu dijalankan oleh rekan/backend agent

```bash
# Run on a machine that can reach the public API:
BASE='https://api.nusamatra.site'
curl -i "$BASE/api/v1/health"
curl -i "$BASE/api/v1/regions?level=kabupaten_kota&q=bogor"
curl -i "$BASE/api/v1/indicators"
curl -i "$BASE/api/v1/boundaries/kabupaten?format=geojson&resolution=low"
curl -i "$BASE/api/v1/indicators/soc_poverty_rate/values"
curl -i -X POST "$BASE/api/v1/indicators/composite-query" \
  -H 'Content-Type: application/json' \
  -d '{"weights":{"dis_multihazard_index":3500,"soc_poverty_rate":2500,"edu_damaged_classrooms_pct":2000,"hlt_stunting_prevalence":2000}}'
curl -i -X POST "$BASE/api/v1/indicators/composite-query" \
  -H 'Content-Type: application/json' \
  -d '{"weights":{"soc_poverty_rate":9000}}'
curl -i -H 'X-Data-Mode: LIVE' "$BASE/api/v1/regions"
```

**Catatan:** output `curl` di atas belum dieksekusi dari mesin yang mempunyai akses; hanya instruksi verifikasi. Untuk LIVE harus memeriksa bukan hanya status 503, tetapi juga header `X-Data-Fallback: UNAVAILABLE` dan tidak ada data DEMO.

## Instruksi kepada Claude Code — Frontend

1. Simpan `openapi.json` sebagai kontrak referensi, bukan bukti API siap LIVE.
2. Pisahkan `apiClient` dari komponen UI/peta; gunakan environment variable `VITE_NUSA_MATRA_API_BASE_URL` atau mekanisme framework yang setara. URL jangan ditanam langsung dalam komponen.
3. Mulai dari health, daftar/search wilayah, katalog indikator, detail wilayah, values, dan composite query. UI harus menandai fixture `DEMO_EXAMPLE` secara jelas.
4. Gunakan tipe runtime validation pada response karena `ApiResponse.data` belum bertipe. Hindari `any` tanpa pemeriksaan.
5. Bangun adapter boundary saat sumber polygon valid benar-benar tersedia; jangan menganggap placeholder GeoJSON valid sebagai polygon.
6. Pegang integer basis points total 10.000 dan pastikan penjumlahan bobot tepat, termasuk edge case pembulatan UI.
7. Tangani HTTP 503 mode LIVE dengan status unavailable yang jelas tanpa fallback otomatis ke DEMO.
8. Tambahkan integrasi CORS/proxy dalam dev config sesuai origin frontend yang benar, bukan whitelist `*` plus credentials.
9. Pertahankan desain Figma, HeroDiorama, Explore3DMap, animasi dan mode Normal/Glass; jangan rebuild Three.js hanya karena belum ada boundary LIVE.
10. Lakukan uji API dengan respons nyata dari endpoint, lalu catat perubahan yang diperlukan backend.

## Bukti dan batas pemeriksaan

Audit ini dilakukan terhadap dokumen `openapi.json` yang diunggah, valid sebagai JSON, dengan 11 path/operasi dan semua `$ref` dapat di-resolve. Pengujian URL publik tidak berhasil dari lingkungan pemeriksa, sehingga tidak ada klaim HTTP 200, live database, geometri valid, lint/typecheck, atau test suite telah diverifikasi di sini.
