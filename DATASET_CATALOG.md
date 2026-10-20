# NUSA MATRA — OFFICIAL DATASET CATALOG (2026)

**Document ID:** `NM-DH-01`  
**Target Platform:** Nusa Matra — Geographic Decision-Support System (WIA 2026)  
**Scope:** Verified Official Indonesian Government Data Sources (Kabupaten/Kota Priority)  
**Last Verified:** October 2026  

---

## 1. Executive Summary & Verification Policy

Dokumen ini memuat katalog sumber data resmi pemerintah Indonesia yang telah diverifikasi untuk menyuplai **Nusa Matra Data Hub**. Seluruh endpoint, metode akses, syarat autentikasi, cakupan spasial, serta batasan teknis dicatat sesuai kondisi produksi aktual tanpa mengasumsikan akses publik pada sistem yang dikunci.

| Agency | Primary Domain | Granularity | Auth Required | Programmatic Access Method |
| :--- | :--- | :--- | :---: | :--- |
| **BPS** | Demografi, Kemiskinan, IPM, Infrastruktur Dasar | Nasional, Provinsi (38), Kab/Kota (514) | **Ya** (Free API Key) | REST JSON API (`webapi.bps.go.id`) |
| **SIG-BPS** | Tabel Bridging Kode Wilayah (BPS $\leftrightarrow$ Kemendagri) | Provinsi (38) s.d. Desa (~83.971) | **Tidak** | Web XHR JSON & Master CSV/XLSX (`sig.bps.go.id`) |
| **BNPB (Satu Data)** | Kejadian Bencana Historis & Tabel IRBI | Provinsi (38), Kab/Kota (514) | **Tidak** | Open CKAN API v3 (`data.bnpb.go.id`) |
| **BNPB (InaRISK)** | Peta Bahaya & Risiko Multi-Bencana (Raster/Vektor) | Grid 100m $\times$ 100m & Kab/Kota | **Tidak** | ArcGIS REST `ImageServer` / `MapServer` (`gis.bnpb.go.id`) |
| **BIG** | Batas Wilayah Administrasi Resmi (RBI) | Provinsi (38), Kab/Kota (514), Kecamatan, Desa | **Ya** (Akun Portal) | Unduh GPKG/SHP (`tanahair.indonesia.go.id`) & WMS/ArcGIS REST |
| **Kemendikdasmen** | Statistik Sekolah, Guru, Ruang Kelas, APM/APK | Provinsi (38), Kab/Kota (514), Sekolah | **Tidak** | Unduh Batch XLSX/CSV (`data.kemendikdasmen.go.id`) & XHR Dapodik |
| **Kemenkes & SDI** | Stunting (SKI/SSGI), Faskes, Rasio Tenaga Medis | Provinsi (38), Kab/Kota (514) | **Tidak** | CKAN API & Batch File (`data.go.id` & Profil Kesehatan) |

---

## 2. Badan Pusat Statistik (BPS) — Demographics, Socioeconomics & Basic Services

### 2.1 BPS WebAPI (Dynamic Tables, Strategic Indicators & Publications)
* **URL Portal Resmi:** `https://webapi.bps.go.id/developer/`
* **Base Endpoint API:** `https://webapi.bps.go.id/v1/api/`
* **Metode Akses:** REST API (JSON) melalui HTTPS. **Wajib Autentikasi:** Memerlukan registrasi akun pengembang gratis untuk mendapatkan parameter `key` (`?key={BPS_API_KEY}`).
* **Endpoint Utama yang Diverifikasi:**
  * Daftar Domain Wilayah: `GET https://webapi.bps.go.id/v1/api/domain/type/all/key/{api_key}/`
  * Indikator Strategis: `GET https://webapi.bps.go.id/v1/api/list/model/statictable/domain/{domain_id}/key/{api_key}/`
  * Tabel Dinamis (Subject/Variable Matrix): `GET https://webapi.bps.go.id/v1/api/list/model/data/domain/{domain_id}/var/{var_id}/key/{api_key}/`
* **Granularitas Geografis:** Nasional (`0000`), Provinsi (38 provinsi, kode 2 digit + `00`), Kabupaten/Kota (514 kabupaten/kota, kode domain 4 digit BPS).
* **Tahun Data Terbaru:** Rilis tahunan penuh 2025 (Susenas Maret 2025, Sakernas Agustus 2025, IPM 2025, PDRB 2025); rilis triwulanan 2026; serta Pendataan Potensi Desa (Podes) 2024.
* **Lisensi:** Data Terbuka Pemerintah (BPS Terms of Use — bebas digunakan untuk riset dan aplikasi publik dengan wajib mencantumkan atribusi *Sumber: Badan Pusat Statistik*).
* **Frekuensi Pembaruan:** Tahunan untuk indikator Susenas/IPM/Kemiskinan (dirilis Q1–Q2 tahun berikutnya); Triwulanan untuk PDRB; Tiga tahunan untuk Podes.
* **Identifier Utama:** `domain_id` (4 digit kode wilayah BPS, contoh: `3273` untuk Kota Bandung), `var_id` (ID Variabel), `turvar_id` (ID Turunan Variabel), `th_id` (ID Tahun).
* **Batasan Teknis & Risiko:**
  1. Penomoran `var_id` bersifat lokal pada masing-masing `domain_id` kantor BPS daerah. **Praktik Terbaik:** Tarik tabel kompilasi nasional yang dirinci menurut Kabupaten/Kota pada `domain=0000` (Pusat) agar tidak perlu memetakan 514 `var_id` lokal yang berbeda-beda.
  2. Memiliki pembatasan laju (*rate limit*) dan waktu respons bervariasi ($300\text{ ms} - 2500\text{ ms}$), sehingga tidak boleh dipanggil langsung oleh aplikasi frontend pengguna.

### 2.2 Sistem Informasi Geografis BPS (SIG-BPS) & Bridging Kode Wilayah
* **URL Resmi:** `https://sig.bps.go.id/` dan `https://sig.bps.go.id/bridging-kode/index`
* **Metode Akses:** Aplikasi web interaktif, endpoint XHR JSON internal penyedia tabel relasi kode, serta unduhan tabel referensi Master File Desa (MFD). Tidak memerlukan autentikasi, namun dilindungi WAF terhadap *request* berfrekuensi tinggi.
* **Granularitas Geografis:** Provinsi (38), Kabupaten/Kota (514), Kecamatan (~7.288), Desa/Kelurahan (~83.971).
* **Tahun Data Terbaru:** Semester 1 Tahun 2026 (selaras dengan Kepmendagri No. 300.2.2-2138 Tahun 2025 dan perubahannya Kepmendagri No. 300.2.2-2430 Tahun 2025).
* **Lisensi:** Standar Referensi Wilayah Pemerintahan Terbuka.
* **Frekuensi Pembaruan:** Semesteran (2 kali setahun).
* **Identifier Utama:** `kode_bps` (string numerik tanpa titik: 2 digit Provinsi, 4 digit Kab/Kota) dan `kode_dagri` (string dengan titik pemisah: `XX.XX`).
* **Batasan Teknis:** Merupakan satu-satunya rujukan resmi untuk menghubungkan statistik BPS ke poligon batas wilayah Kemendagri/BIG karena urutan penomoran kabupaten dalam satu provinsi sering berbeda antara BPS dan Kemendagri di luar Pulau Jawa.

---

## 3. Badan Nasional Penanggulangan Bencana (BNPB) — Disaster Exposure & Risk

### 3.1 Satu Data Bencana Indonesia (CKAN Open Data Portal)
* **URL Portal Resmi:** `https://data.bnpb.go.id/`
* **Base Endpoint API:** `https://data.bnpb.go.id/api/3/action/`
* **Metode Akses:** CKAN Action API v3 (REST JSON) terbuka + unduhan langsung berkas CSV/XLSX/GeoJSON. **Tidak memerlukan autentikasi** untuk membaca katalog dan mengunduh dataset publik.
* **Endpoint Utama yang Diverifikasi:**
  * Pencarian Paket Data: `GET https://data.bnpb.go.id/api/3/action/package_search?q=kompilasi+data+kejadian`
  * Pencarian Indeks Risiko: `GET https://data.bnpb.go.id/api/3/action/package_search?q=indeks+risiko+bencana`
  * Detail Paket & URL Resource: `GET https://data.bnpb.go.id/api/3/action/package_show?id={package_id}`
* **Granularitas Geografis:** Kabupaten/Kota (514) dan Provinsi (38); catatan kejadian menyertakan nama Kecamatan/Desa dan titik koordinat bila tersedia.
* **Tahun Data Terbaru:** *Kompilasi Data Kejadian dan Dampak Bencana Tahun 2025* (terverifikasi penuh) serta pembaruan berjalan 2026; tabel *Indeks Risiko Bencana Indonesia (IRBI)* 2024/2025.
* **Lisensi:** Lisensi Terbuka Satu Data Indonesia (Peraturan BNPB No. 7 Tahun 2023 tentang Petunjuk Pelaksanaan Standar Data Kejadian dan Dampak Bencana).
* **Frekuensi Pembaruan:** Bulanan/Tahunan untuk kompilasi kejadian; Tahunan untuk skor IRBI.
* **Identifier Utama:** `kode_kabupaten` / `kode_wilayah` (4 digit), `id_bencana`, `jenis_bencana`, `tanggal_kejadian`.
* **Batasan Teknis:** Berkas CSV historis terkadang mencampur format kode wilayah bertitik (`32.01`) dan tanpa titik (`3201`), serta masih menggunakan kode Provinsi Papua lama (`91`/`94`) untuk rekaman sebelum tahun 2023.

### 3.2 BNPB Geoportal & InaRISK ArcGIS REST Services
* **URL Portal Resmi:** `https://inarisk.bnpb.go.id/` dan `https://gis.bnpb.go.id/`
* **Base Endpoint ArcGIS Server:** `https://gis.bnpb.go.id/server/rest/services/inarisk/`
* **Metode Akses:** ArcGIS REST API (`ImageServer`, `MapServer`, `FeatureServer`), OGC WMS/WCS. Terbuka untuk akses baca publik (`?f=pjson`).
* **Layanan Spasial Utama yang Diverifikasi:**
  * Bahaya Banjir: `.../inarisk/INDEKS_BAHAYA_BANJIR/ImageServer`
  * Bahaya Gempabumi: `.../inarisk/INDEKS_BAHAYA_GEMPABUMI/ImageServer`
  * Bahaya Tanah Longsor: `.../inarisk/INDEKS_BAHAYA_TANAH_LONGSOR/ImageServer`
  * Bahaya Tsunami: `.../inarisk/INDEKS_BAHAYA_TSUNAMI/ImageServer`
  * Bahaya Kebakaran Hutan dan Lahan: `.../inarisk/INDEKS_BAHAYA_KARHUTLA/ImageServer`
  * Indeks Risiko Multi-Bencana: `.../inarisk/INDEKS_RISIKO_BENCANA/MapServer`
* **Granularitas Geografis:** Grid Raster $100\text{ m} \times 100\text{ m}$ (cakupan nasional) dengan nilai indeks kontinu $0.0 - 1.0$.
* **Tahun Data Terbaru:** Layer dasar IRBI 2024/2025 yang aktif digunakan pada tahun 2026.
* **Lisensi:** Data Geospasial Terbuka Pemerintah (Pusdatinkom BNPB).
* **Batasan Teknis:** Mayoritas layer bahaya disajikan sebagai `ImageServer` (raster piksel), bukan tabel vektor poligon Kabupaten/Kota. Untuk menghasilkan angka indeks rata-rata per Kabupaten/Kota bagi API tabular, Data Hub harus mengekstrak statistik zonal (*zonal statistics*) secara *offline* dengan memotongkan raster terhadap poligon batas Kabupaten/Kota BIG, atau mengambil tabel skor IRBI resmi dari `data.bnpb.go.id`. Server sekunder `inarisk1.bnpb.go.id:6443` sering mengalami kendala sertifikat SSL dan *timeout*, sehingga wajib mengutamakan `gis.bnpb.go.id`.

---

## 4. Badan Informasi Geospasial (BIG) — Administrative Boundaries

### 4.1 Ina-Geoportal (TanahAir Indonesia) — Batas Wilayah & Rupabumi Indonesia (RBI)
* **URL Portal Resmi:** `https://tanahair.indonesia.go.id/`
* **URL Geoservices:** `https://geoservices.big.go.id/rbi/rest/services/BATASWILAYAH/`
* **Metode Akses:**
  * Unduhan paket GeoPackage (`.gpkg`) / Shapefile (`.shp`) via `https://tanahair.indonesia.go.id/portal-web/unduh/` (**Wajib Autentikasi:** Login akun pengguna gratis di portal TanahAir).
  * Layanan OGC WMS / ArcGIS MapServer publik melalui `geoservices.big.go.id`.
* **Granularitas Geografis:** Provinsi (38), Kabupaten/Kota (514), Kecamatan, dan Desa/Kelurahan pada skala 1:250.000, 1:50.000, hingga 1:25.000.
* **Tahun Data Terbaru:** Rilis Batas Wilayah Administrasi Terintegrasi 2024/2025 (telah mencakup 38 Provinsi termasuk pemekaran 4 provinsi baru di Papua).
* **Lisensi:** Kebijakan Satu Peta (*One Map Policy*) / Lisensi Data Geospasial Terbuka BIG (wajib mencantumkan atribusi Badan Informasi Geospasial).
* **Frekuensi Pembaruan:** Tahunan/Periodik mengikuti penetapan Permendagri Batas Daerah dan Kepmendagri Kode Wilayah.
* **Identifier Utama pada Atribut Spasial:**
  * `KDPPUM`: Kode Provinsi Kemendagri (2 digit)
  * `WADMPR`: Nama Wilayah Administrasi Provinsi
  * `KDPKAB`: Kode Kabupaten/Kota Kemendagri (`XX.XX` atau `XXXX`)
  * `KDBPS`: Kode Wilayah BPS (4 digit)
  * `WADMKK`: Nama Wilayah Administrasi Kabupaten/Kota
* **Batasan Teknis:** Geometri mentah skala 1:50.000/1:250.000 untuk seluruh kepulauan Indonesia berukuran sangat besar ($>150\text{ MB}$) dengan ratusan ribu titik verteks pantai. Wajib melalui proses simplifikasi berbasis topologi (`TopoJSON` $< 1.8\text{ MB}$) di dalam Data Hub sebelum dikirim ke engine peta 3D frontend.

---

## 5. Kementerian Pendidikan Dasar dan Menengah (Kemendikdasmen) — Education Access

### 5.1 Portal Data Pendidikan & Neraca Pendidikan Daerah (NPD)
* **URL Portal Resmi:** `https://data.kemendikdasmen.go.id/` (sebelumnya `data.kemdikbud.go.id`)
* **Metode Akses:** Unduhan publik berkas dataset master dalam format XLSX/CSV/PDF (`Statistik Persekolahan 2025/2026`, `Ikhtisar Pendidikan 2025/2026`, `Analisis Sanitasi Sekolah 2025`, `Neraca Pendidikan Daerah`). **Tidak tersedia REST API publik terbuka dengan token pihak ketiga.**
* **Granularitas Geografis:** Provinsi (38) dan Kabupaten/Kota (514).
* **Tahun Data Terbaru:** Tahun Ajaran 2025/2026 (dirilis Maret–April 2026) dan berjalan Semester Ganjil 2026/2027.
* **Lisensi:** Data Terbuka Pemerintah (Pusdatin Kemendikdasmen).
* **Frekuensi Pembaruan:** Semesteran (*cut-off* Oktober untuk Semester Ganjil dan Maret/April untuk Semester Genap).
* **Identifier Utama:** Kode Wilayah internal Kemendikdasmen (6 digit, contoh `020500`) dan Nama Kabupaten/Kota; satuan pendidikan menggunakan `NPSN` (8 digit).

### 5.2 Portal Data Pokok Pendidikan (Dapodik)
* **URL Portal Resmi:** `https://dapo.kemendikdasmen.go.id/`
* **Metode Akses:** Dashboard publik dan endpoint XHR JSON internal (`/rekap/progresSP`, `/rekap/dataSekolah`) yang menyajikan agregasi jumlah sekolah, peserta didik, guru, rombel, dan kondisi ruang kelas per wilayah.
* **Granularitas Geografis:** Provinsi, Kabupaten/Kota, Kecamatan, hingga Satuan Pendidikan ($447.668$ sekolah aktif per Oktober 2026).
* **Tahun Data Terbaru:** Semester Ganjil 2026/2027 (Dapodik versi 2027.b, tingkat sinkronisasi nasional $97,3\%$ per Oktober 2026).
* **Batasan Teknis:** Menggunakan skema kode wilayah internal 6 digit (`010000` untuk DKI Jakarta, `020000` untuk Jawa Barat, dst.) yang **berbeda total** dari kode BPS maupun Kemendagri. Wajib dipetakan menggunakan tabel *cross-walk* `kemendikdasmen_code` di dalam Data Hub.

---

## 6. Kementerian Kesehatan (Kemenkes) & Satu Data Indonesia — Healthcare Access

### 6.1 Portal Satu Data Indonesia (SDI) & Publikasi Profil Kesehatan Kemenkes
* **URL Portal Resmi:** `https://data.go.id/` dan `https://kemkes.go.id/`
* **Metode Akses:** Katalog CKAN REST API (`https://data.go.id/api/`) serta unduhan tabel resmi XLSX/CSV untuk dataset berstatus `Terbuka` (*Profil Kesehatan Indonesia*, *Survei Kesehatan Indonesia / SKI*, dan *SSGI*).
* **Granularitas Geografis:** Provinsi (38) dan Kabupaten/Kota (514).
* **Tahun Data Terbaru:** *Profil Kesehatan Indonesia 2025* (rilis 2026), data prevalensi stunting SKI/SSGI 2024/2025, serta modul kesehatan Susenas BPS 2025.
* **Lisensi:** Satu Data Indonesia (Perpres No. 39 Tahun 2019).
* **Frekuensi Pembaruan:** Tahunan.
* **Identifier Utama:** Kode Kabupaten/Kota (Kemendagri/BPS) dan Nama Wilayah.
* **Batasan Teknis & Klarifikasi Penting:**
  * API klinis **SATUSEHAT** (`https://satusehat.kemkes.go.id/`) berbasis HL7 FHIR R4 bersifat **TERBATAS (Restricted)** — mewajibkan kredensial OAuth2 institusi fasilitas pelayanan kesehatan (`client_id` & `client_secret`) untuk pertukaran rekam medis, bukan untuk agregasi statistik wilayah publik.
  * Oleh karena itu, indikator kesehatan Kabupaten/Kota pada Nusa Matra wajib bersumber dari kompilasi nasional *Profil Kesehatan Indonesia* Kemenkes, tabel *SKI/SSGI*, serta tabel *Susenas Kesehatan & Podes* dari BPS WebAPI agar menjamin kelengkapan 514 Kabupaten/Kota.