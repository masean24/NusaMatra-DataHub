# NUSA MATRA — DATA SOURCE VERIFICATION & RISK AUDIT

**Document ID:** `NM-DH-04`  
**Target Platform:** Nusa Matra — Geographic Decision-Support System (WIA 2026)  
**Scope:** Endpoint Availability, Authentication Requirements, Operational Risks & Engineering Safeguards  

---

## 1. Matriks Hasil Verifikasi Sumber Data Resmi (Oktober 2026)

| Instansi & Sistem | URL Portal / Endpoint | Status Verifikasi | Wajib Auth? | Stabilitas & Batasan Operasional | Strategi Ingesti Nusa Matra |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **BPS WebAPI** | `https://webapi.bps.go.id/v1/api/` | **TERVERIFIKASI AKTIF** | **YA** (`key` token gratis) | Latensi $300-2500\text{ ms}$; memiliki *rate limiter* jika dipanggil paralel berlebihan. | Worker terjadwal menarik tabel kompilasi Kab/Kota (`domain=0000`) ke PostgreSQL secara *batch*. |
| **SIG-BPS Bridging Kode** | `https://sig.bps.go.id/bridging-kode/index` | **TERVERIFIKASI AKTIF** | **TIDAK** | Dilindungi WAF terhadap *scraping* agresif; struktur mengikuti rilis MFD semesteran. | Impor tabel master relasi kode ke `dim_regions` setiap semester (2x setahun). |
| **BNPB Satu Data (CKAN)** | `https://data.bnpb.go.id/api/3/action/` | **TERVERIFIKASI AKTIF** | **TIDAK** | Sangat stabil ($\sim 2.830$ dataset); mendukung pencarian metadata & unduhan CSV/XLSX. | Konektor Python CKAN mengambil CSV kompilasi kejadian & tabel IRBI Kab/Kota. |
| **BNPB GIS (InaRISK)** | `https://gis.bnpb.go.id/server/rest/services/inarisk/` | **TERVERIFIKASI AKTIF** | **TIDAK** | Node utama `gis.bnpb.go.id` stabil; node sekunder `inarisk1.bnpb.go.id:6443` sering gagal SSL/*timeout*. | Ekstraksi *zonal statistics* raster `ImageServer` terhadap poligon Kab/Kota dilakukan secara *offline* saat ETL. |
| **BIG Ina-Geoportal** | `https://tanahair.indonesia.go.id/` | **TERVERIFIKASI AKTIF** | **YA** (Login portal untuk unduh GPKG/SHP) | Unduhan berkas batas wilayah memerlukan sesi autentikasi; layanan WMS terkadang lambat saat jam kerja. | Unduh GPKG Batas Wilayah resmi setiap ada rilis Kepmendagri baru, simpan di Object Storage, dan proses via PostGIS. |
| **Kemendikdasmen Data** | `https://data.kemendikdasmen.go.id/` | **TERVERIFIKASI AKTIF** | **TIDAK** | Tidak menyediakan REST API publik untuk pihak ketiga; publikasi berupa berkas master XLSX/CSV/PDF. | Pipeline *semi-automated* mem-parsing rilis berkas *Statistik Persekolahan* & *NPD* setiap semester. |
| **Kemendikdasmen Dapodik** | `https://dapo.kemendikdasmen.go.id/` | **TERVERIFIKASI AKTIF** | **TIDAK** | Endpoint XHR internal (`/rekap/progresSP`) tidak memiliki kontrak SLA publik dan dapat berubah antar-versi Dapodik. | Scraper terjadwal dengan jeda sopan (*rate-limited* $1\text{ req} / 2\text{ dtk}$) menyimpan salinan mentah ke staging. |
| **Satu Data Indonesia** | `https://data.go.id/` | **TERVERIFIKASI AKTIF** | **TIDAK** (Dataset `Terbuka`) | Skema kolom CSV dari pemerintah daerah sering tidak seragam antar-kabupaten. | Hanya gunakan dataset cakupan nasional yang diterbitkan kementerian pusat (Kemenkes, Bappenas, BPS). |
| **Kemenkes SATUSEHAT** | `https://satusehat.kemkes.go.id/` | **TERBATAS (RESTRICTED)** | **YA** (OAuth2 Fasyankes) | Dirancang khusus untuk interoperabilitas rekam medis elektronik FHIR R4, **bukan** API statistik wilayah publik. | **DILARANG DIGUNAKAN** untuk indikator publik. Gunakan *Profil Kesehatan Indonesia*, SKI/SSGI, dan Susenas BPS. |

---

## 2. Daftar Informasi yang Dinyatakan Tidak Tersedia (Explicitly Unavailable)

Sesuai prinsip transparansi data, indikator berikut telah dievaluasi dan dinyatakan **TIDAK TERSEDIA (`UNAVAILABLE`)** dari sumber terbuka pemerintah sehingga tidak boleh diklaim atau dipalsukan:

1. **Waktu Tempuh Riil Rumah-ke-Sekolah per Siswa (`edu_school_travel_time_p90`):**
   * *Alasan:* Koordinat alamat rumah siswa di dalam Dapodik dilindungi sebagai Data Pribadi (UU PDP) dan tidak dibuka ke publik.
   * *Mitigasi Resmi:* Gunakan indikator proksi resmi dari **Podes BPS** (rata-rata jarak/kemudahan akses desa ke SMP/SMA terdekat) serta **Persentase Ruang Kelas Rusak** dan **APM**.
2. **Keterisian Tempat Tidur ICU Rumah Sakit Real-Time per Kabupaten (`hlt_realtime_icu_occupancy`):**
   * *Alasan:* Memerlukan integrasi kredensial internal SIRS/SATUSEHAT Kemenkes yang tidak dibuka sebagai API analitik historis publik.
   * *Mitigasi Resmi:* Gunakan **Rasio RS & Puskesmas per 10.000 Penduduk** (`hlt_facilities_per_10k`) dan **Rasio Dokter per 10.000 Penduduk** (`hlt_doctors_per_10k`).

---

## 3. Protokol Pengamanan Ingesti (Mandatory Engineering Guardrails)

1. **Isolasi Penuh Frontend dari Endpoint Pemerintah (Zero Upstream Runtime Dependency):**
   Aplikasi React dan peta 3D Nusa Matra **dilarang keras** memanggil API BPS, BNPB, BIG, atau Kemendikdasmen secara langsung dari browser pengguna. Seluruh permintaan data frontend wajib dilayani oleh **Nusa Matra Data Hub API** dari snapshot yang telah dinormalisasi dan di-cache.
2. **Pengarsipan Bukti Mentah dengan Hash Kriptografis (Raw Payload Archiving):**
   Setiap kali worker ingesti mengunduh respons JSON dari BPS/BNPB atau berkas XLSX dari Kemendikdasmen, berkas asli wajib disimpan ke *Object Storage* (`/raw/{agency}/{yyyy-mm-dd}/{filename}`) dan dihitung nilai hash **SHA-256**-nya ke dalam tabel `dim_datasets.raw_sha256`. Hal ini menjamin ketertelusuran audit (*auditability*) 100%.
3. **Karantina Baris Tidak Terpetakan (`etl_quarantine_rows`):**
   Apabila sebuah baris data dari berkas eksternal gagal dipetakan ke salah satu dari 514 `region_id` kanonis (misalnya akibat kesalahan ketik nama kabupaten pada tabel Excel kementerian), baris tersebut tidak boleh dihapus diam-diam maupun dimasukkan paksa, melainkan dialihkan ke tabel `etl_quarantine_rows` dan memicu peringatan pada log ETL.