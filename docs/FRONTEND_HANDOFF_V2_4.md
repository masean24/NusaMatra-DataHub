# FRONTEND HANDOFF v2.4 — Error Envelope and Boundary Metadata

Status: implemented in the working tree. Contract samples:
`docs/staging_samples/contract_v2_4/`.

Tidak ada field lama yang diganti nama atau diubah artinya. Perubahan di bawah
ini additive, kecuali bentuk error validasi yang memang diseragamkan.

---

## 1. Semua error memakai amplop yang sama

Semua `422` sekarang memakai bentuk:

```json
{
  "status": "error",
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed.",
  "detail": "query.level: String should match pattern '^(kabupaten_kota|provinsi|all)$'"
}
```

Validasi bobot composite memakai code khusus:

```json
{
  "status": "error",
  "code": "WEIGHT_VALIDATION_ERROR",
  "message": "body.weights: Weights must sum to 10000 basis points, got 8000",
  "detail": "body.weights: Weights must sum to 10000 basis points, got 8000"
}
```

Perubahan:

- `{"detail": [...]}` bawaan FastAPI sudah tidak dipakai.
- `{"detail": {"code": "...", "message": "..."}}` pada composite sudah tidak dipakai.
- `detail` sekarang string yang bisa langsung ditampilkan.
- `404`, `405`, `413`, `429`, `503` juga memakai `status`, `code`, `message`.

Kode error yang umum:

| HTTP | code |
|---|---|
| 400 | `BAD_REQUEST` |
| 401 | `UNAUTHORIZED` |
| 403 | `FORBIDDEN` |
| 404 | `NOT_FOUND` |
| 405 | `METHOD_NOT_ALLOWED` |
| 413 | `PAYLOAD_TOO_LARGE` |
| 422 | `VALIDATION_ERROR` / `WEIGHT_VALIDATION_ERROR` |
| 429 | `RATE_LIMITED` |
| 503 | `SERVICE_UNAVAILABLE` |

---

## 2. `meta.boundary_version` selalu terisi

Semua endpoint berbasis snapshot sekarang mengisi:

```json
"meta": {
  "snapshot_id": "2026.10.0-live-0de6ac68f0d55b3a",
  "mode": "LIVE",
  "boundary_version": "BIG-20260601"
}
```

Nilainya diambil dari `data_snapshots.boundary_version`, bukan hardcode. Jadi
snapshot lama dan snapshot baru bisa berbeda bila batas wilayahnya berbeda.

Endpoint yang sudah dicek:

- `GET /indicators/coverage`
- `GET /indicators/{id}/values`
- `GET /datasets`
- `GET /snapshots`
- `GET /regions`
- `GET /boundaries/*`
- `POST /indicators/composite-query`

---

## 3. Penanda snapshot aktif

`GET /snapshots` memakai field:

```json
{
  "snapshot_id": "2026.10.0-live-0de6ac68f0d55b3a",
  "is_active_default": true
}
```

Tidak ada field `status`, `is_active`, atau `active`. Gunakan
`data[].is_active_default`.

---

## 4. CORS produksi

CORS diatur lewat environment Coolify, bukan lewat kode:

```env
NM_CORS_ORIGINS=https://domain-fe-produksi,https://api.orangkeren.me
```

Origin Codespace dan `localhost` hanya untuk development. Sebelum rilis publik,
hapus origin development dari env produksi. Kirim origin FE final ke backend.

---

## 5. Rate limiter

Rate limiter masih `NM_RATE_LIMIT_REPORT_ONLY=true`. Response belum mengembalikan
`429`; header `X-RateLimit-*` tetap dikirim.

Sebelum enforcement diaktifkan:

1. FE pastikan `429` tampil sebagai pesan yang jelas.
2. FE membaca `Retry-After`.
3. Backend set `NM_RATE_LIMIT_REPORT_ONLY=false`.

---

## 6. Preset aspal

`inf_asphalt_road_village_pct` masih ada di preset
`bencana_infrastruktur` dengan bobot statis 25%. Server sudah mengirim:

- `availability.unavailable_indicators`
- `availability.effective_weights`
- `availability.coverage_weight_pct`
- `availability.rankable`

Jangan hapus indikator dari preset lama. Bobot preset masuk ke
`compute_content_digest()`, sehingga mengubahnya bisa membuat verifikasi digest
snapshot lama gagal. Kalau indikator harus dikeluarkan, buat preset baru
(`bencana_infrastruktur_v2`) dan biarkan preset lama untuk snapshot historis.

---

## 7. Arah persentil indikator

Semua response sekarang membawa:

```json
"meta": {
  "score_direction": "higher_is_need"
}
```

`GET /api/v1/regions/{region_id}` juga mengirim `polarity` pada setiap item
`indicators[]`:

```json
{
  "indicator_id": "soc_hdi",
  "raw_value": 69.1,
  "polarity": "positive",
  "normalized_score": 37.49,
  "national_percentile": 72.71,
  "national_rank": 141
}
```

Arti persentil:

- `national_percentile` adalah **persentil kebutuhan**, bukan persentil nilai mentah.
- `higher_is_need`: persentil tinggi berarti kebutuhan intervensi lebih tinggi.
- `polarity` menjelaskan arah nilai mentah: `positive` berarti nilai mentah tinggi
  lebih baik; `negative` berarti nilai mentah tinggi lebih buruk.

Contoh: IPM `69,1` dengan `polarity: positive` dan persentil `72,71` berarti
kebutuhan relatif tinggi, bukan “IPM lebih tinggi dari 72,71% wilayah”.
Frontend tidak perlu lagi menampilkan “Tidak dinilai” bila ketiga field ini ada.

## 8. QA checklist

- `GET /api/v1/regions?level=invalid` → `422 VALIDATION_ERROR`, bukan array.
- `POST /api/v1/indicators/composite-query` dengan total bobot 8000 →
  `422 WEIGHT_VALIDATION_ERROR`, `message` berisi `10000`.
- `GET /api/v1/indicators/does_not_exist/values` → `404 NOT_FOUND`.
- `GET /api/v1/indicators/coverage?mode=live` → `meta.boundary_version` terisi.
- `GET /api/v1/indicators/{id}/values?mode=live` → `meta.boundary_version` terisi.
- `GET /api/v1/snapshots?mode=live` → item aktif punya
  `is_active_default: true`.
- `GET /api/v1/regions/{id}?mode=live` → `meta.score_direction` terisi dan
  setiap item `indicators[]` punya `polarity`.
