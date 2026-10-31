# Handoff FE — Stunting SSGI 2024

> **Superseded:** untuk update data terbaru (IPM/UHH 2025, IRBI 2025, pendidikan 2025, DIBI 2025), gunakan [FRONTEND_HANDOFF_2025_REFRESH.md](../../frontend/FRONTEND_HANDOFF_2025_REFRESH.md). Dokumen ini disimpan sebagai riwayat perubahan stunting.

## Snapshot aktif

```text
2026.10.0-live-c68381fcca708ecf
```

Snapshot lama tetap immutable dan masih bisa diakses lewat `snapshot_id` lama. Hanya snapshot baru yang menjadi `is_active_default`.

## Yang berubah

| Item | Sebelum | Sesudah |
|---|---|---|
| Sumber stunting | Kemenkes SKI 2023 | **Kemenkes SSGI 2024** |
| `dataset_id` | `kemenkes_ski_2023` | **`kemenkes_ssgi_2024`** |
| `reference_year` | 2023 | **2024** |
| Coverage | 487/514 | **514/514** |
| `national_min` | 1.6 | **5.2** |
| `national_max` | 50.2 | **56.8** |
| Missing stunting | 27 kab/kota | **0** |

Tidak ada perubahan bentuk response API. Field yang sudah ada tetap sama:

```json
{
  "raw": 36.0,
  "norm": 59.69,
  "pct": 93.37,
  "rank": 35,
  "flag": "VERIFIED",
  "dataset_id": "kemenkes_ssgi_2024",
  "source_record_ref": "Kemenkes SSGI 2024 p.61"
}
```

## Dampak ranking komposit

Preset `kemiskinan_stunting` berubah cukup besar karena batas normalisasi dan 27 nilai baru. Ranking top 5 sekarang:

1. Kabupaten Mamberamo Tengah — `81.50`, coverage `100%`
2. Kabupaten Nduga — `80.19`, coverage `100%`
3. Kabupaten Tolikara — `80.14`, coverage `100%`
4. Kabupaten Puncak — `79.12`, coverage `80%` (sanitasi belum tersedia)
5. Kabupaten Lanny Jaya — `74.34`, coverage `100%`

Nduga sekarang **tidak lagi** menampilkan “data stunting tidak tersedia”.

## Yang perlu dilakukan di FE

1. **Jangan hardcode snapshot lama.** Ambil snapshot aktif dari:
   - `GET /api/v1/health?mode=live` → `active_snapshot` (top-level)
   - atau `GET /api/v1/snapshots`
2. Ganti copy/label `SKI 2023` menjadi **`SSGI 2024`**.
3. Ganti copy `507 kab/kota` menjadi **`514 kab/kota`**.
4. Kalau ada color scale atau skala peta yang memakai batas lama `1.6–50.2`, ganti ke **`5.2–56.8`** atau ambil dari metadata indikator.
5. Bersihkan cache/persisted state yang menyimpan:
   - snapshot ID lama,
   - nilai stunting lama,
   - ranking komposit lama.
6. Jangan hardcode ranking/top 5. Data top 5 berubah; selalu render dari response API.
7. Tampilkan `dataset_id` dan `source_record_ref` di tooltip/provenance kalau sudah ada.
8. Untuk Puncak, tetap tampilkan coverage `80%` dan missing indicator sanitasi—jangan dipaksa `100%`.
9. Mode **DEMO tidak berubah**; perubahan ini hanya untuk snapshot **LIVE**.

## Copy-paste untuk teman FE

```text
Backend stunting sudah pindah ke SSGI 2024. Snapshot aktif:
2026.10.0-live-c68381fcca708ecf

Yang berubah:
- dataset_id: kemenkes_ssgi_2024
- reference_year: 2024
- coverage: 514/514 kab/kota (sebelumnya 487)
- national_min/max: 5.2 / 56.8
- 27 daerah yang sebelumnya kosong sekarang terisi; Nduga = 36.0%
- response API tidak berubah bentuknya

Tolong:
1. Jangan hardcode snapshot lama; ambil active snapshot dari /api/v1/health?mode=live
2. Ganti label SKI 2023 -> SSGI 2024 dan 507 -> 514
3. Update color scale kalau masih pakai 1.6–50.2 -> 5.2–56.8
4. Clear cache ranking/nilai stunting lama
5. Jangan hardcode top 5; ranking kemiskinan_stunting berubah
6. Cek Nduga: sekarang coverage 100%, bukan data unavailable
7. Puncak tetap 80% coverage karena sanitasi belum ada

Top 5 sekarang: Mamberamo Tengah 81.50, Nduga 80.19, Tolikara 80.14, Puncak 79.12, Lanny Jaya 74.34.
```

## Sumber data

- Kemenkes BKPK — *Survei Status Gizi Indonesia (SSGI) 2024 Dalam Angka*
- PDF tabel halaman 44–61, Tabel 4.3–4.40
- File turunan: `data/kemenkes_ssgi_2024_stunting.csv`
- Provenance: `data/kemenkes_ssgi_2024_stunting.provenance.json`
