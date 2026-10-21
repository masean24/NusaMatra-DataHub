# NUSA MATRA — GEOGRAPHY, ADMINISTRATIVE BOUNDARIES & REGION CODE BRIDGING

**Document ID:** `NM-DH-03`  
**Target Platform:** Nusa Matra — Geographic Decision-Support System (WIA 2026)  
**Scope:** Administrative Hierarchy, Legal Boundary Versions, and Multi-Agency Code Crosswalk  

---

## 1. Masalah Utama Perbedaan Kode Wilayah di Indonesia

Instansi pemerintah Indonesia **tidak menggunakan satu kode *primary key* tunggal** yang seragam untuk Kabupaten/Kota. Menggabungkan batas geospasial (BIG), statistik sosial-ekonomi (BPS), data risiko bencana (BNPB), dan data pendidikan (Kemendikdasmen) secara langsung tanpa tabel jembatan (*bridging table*) akan menyebabkan kegagalan *join* pada puluhan kabupaten di luar Pulau Jawa dan di wilayah pemekaran Papua.

Oleh karena itu, Nusa Matra Data Hub menetapkan satu tabel entitas referensi kanonis (`dim_regions`) yang menyimpan pemetaan eksplisit antar sistem pengkodean untuk **38 Provinsi** dan **514 Kabupaten/Kota**.

---

## 2. Versi Regulasi Wilayah Administrasi & Pemekaran Papua (Standar 2025–2026)

### 2.1 Dasar Hukum Aktif
* **Keputusan Menteri Dalam Negeri (Kepmendagri) Nomor 300.2.2-2138 Tahun 2025** (ditetapkan 25 April 2025) beserta perubahannya **Kepmendagri Nomor 300.2.2-2430 Tahun 2025** (ditetapkan 23 Juni 2025) *tentang Pemberian dan Pemutakhiran Kode, Data Wilayah Administrasi Pemerintahan, dan Pulau* (menggantikan Kepmendagri No. 100.1.1-6117 Tahun 2022).
* **Total Cakupan Wilayah Administrasi (Oktober 2026):**
  * **Provinsi:** $38$ Provinsi
  * **Kabupaten:** $416$ Kabupaten (termasuk 1 Kabupaten Administrasi Kepulauan Seribu)
  * **Kota:** $98$ Kota (termasuk 5 Kota Administrasi di DKI Jakarta)
  * **Total Kabupaten/Kota:** **$514$ Unit**

### 2.2 Penanganan Khusus Pemekaran 6 Provinsi di Wilayah Papua
Berdasarkan UU No. 14, 15, 16, dan 29 Tahun 2022 serta pemutakhiran kode wilayah Kemendagri dan Master File Desa (MFD) BPS, sebanyak 29 Kabupaten/Kota di tanah Papua mengalami perubahan 2 digit kode provinsi induknya dibanding dataset historis (2020–2022):

| Nama Provinsi | Kode Kemendagri | Kode BPS | Ibu Kota & Cakupan Kabupaten/Kota |
| :--- | :---: | :---: | :--- |
| **Papua** (Induk) | `91` | `94` / `91` | Jayapura (Kota Jayapura, Kab. Jayapura, Keerom, Sarmi, Mamberamo Raya, Biak Numfor, Supiori, Kepulauan Yapen, Waropen) |
| **Papua Barat** | `92` | `91` / `92` | Manokwari (Kab. Manokwari, Manokwari Selatan, Pegunungan Arfak, Fakfak, Kaimana, Teluk Bintuni, Teluk Wondama) |
| **Papua Selatan** | `93` | `93` | Merauke (Kab. Merauke, Boven Digoel, Mappi, Asmat) |
| **Papua Tengah** | `94` | `94` / `95` | Nabire (Kab. Nabire, Paniai, Mimika, Puncak Jaya, Dogiyai, Intan Jaya, Deiyai, Puncak) |
| **Papua Pegunungan** | `95` | `95` / `96` | Jayawijaya (Kab. Jayawijaya, Pegunungan Bintang, Yahukimo, Tolikara, Mamberamo Tengah, Yalimo, Lanny Jaya, Nduga) |
| **Papua Barat Daya** | `96` | `96` / `92` | Sorong (Kota Sorong, Kab. Sorong, Sorong Selatan, Raja Ampat, Tambrauw, Maybrat) |

> **Aturan Ingesti:** Saat mengimpor data deret waktu historis (misalnya kejadian bencana BNPB 2021–2022), kode lama (seperti Kab. Merauke `9401` atau `91.01`) **wajib** diterjemahkan melalui kolom `legacy_codes` ke kode kanonis aktif saat ini (`9301` / `93.01`).

---

## 3. Perbandingan Sistem Kode Antar-Instansi

| Sistem Kode | Format Provinsi / Kab-Kota | Contoh (Kab. Bogor) | Contoh (Kota Bogor) | Karakteristik & Aturan Konvensi |
| :--- | :--- | :---: | :---: | :--- |
| **Kemendagri (Kode Wilayah Administrasi)** | `XX` / `XX.XX` (4 digit dengan titik) | `32.01` | `32.71` | Digit ke-3 & ke-4 bernilai `01`–`69` untuk **Kabupaten**, dan `71`–`99` untuk **Kota**. Digunakan oleh atribut `KDPKAB` BIG dan Satu Data Indonesia. |
| **BPS (Kode Wilayah Kerja Statistik / MFD)** | `XX` / `XXXX` (4 digit tanpa titik) | `3201` | `3271` | Identik dengan Kemendagri di Pulau Jawa, **namun berbeda pada sejumlah kabupaten di Sumatera, Kalimantan, Sulawesi, dan Papua** karena perbedaan urutan historis pembentukan wilayah sensus. |
| **Kemendikdasmen (Kode Wilayah Dapodik)** | `XXXXXX` (6 digit berhirarki) | `020500` | `026100` | Sistem penomoran internal tersendiri (`010000` = DKI Jakarta, `020000` = Jawa Barat, dst.). **Tidak dapat dikonversi dengan rumus string** ke kode BPS/Kemendagri. |

### 3.1 Mengapa `REPLACE(kode_dagri, '.', '')` Tidak Boleh Digunakan Secara Naif
Menghapus tanda titik dari kode Kemendagri tidak selalu menghasilkan kode BPS yang benar. Sebagai contoh, terdapat kabupaten di luar Jawa yang memiliki kode Kemendagri `XX.04` tetapi tercatat sebagai `XX06` di dalam tabel BPS karena perbedaan waktu registrasi kabupaten pemekaran.
* **Solusi Wajib:** Gunakan tabel referensi resmi dari **SIG-BPS Bridging Kode** (`https://sig.bps.go.id/bridging-kode/index`) untuk mengisi pasangan eksplisit `kemendagri_code` dan `bps_code` pada tabel `dim_regions`.

---

## 4. Standar Identitas Wilayah Kanonis Nusa Matra

Untuk menjaga konsistensi antara database, API, dan engine peta 3D:
1. **Primary Key Kanonis (`region_id`):** Menggunakan **4 digit kode Kemendagri tanpa titik** (`CHAR(4)`, contoh: `3201` untuk Kab. Bogor, `3271` untuk Kota Bogor) untuk tingkat Kabupaten/Kota, dan **2 digit kode Kemendagri** (`CHAR(2)`, contoh: `32` untuk Jawa Barat) untuk tingkat Provinsi.
2. **Atribut Cross-Walk Wajib pada `dim_regions`:**
   * `region_id`: `'3201'` (Primary Key internal & kunci join GeoJSON/TopoJSON)
   * `kemendagri_code`: `'32.01'` (Format resmi bertitik sesuai Kepmendagri 2025)
   * `bps_code`: `'3201'` (Kunci query parameter `domain` pada BPS WebAPI)
   * `kemendikdasmen_code`: `'020500'` (Kunci pemetaan rekapitulasi Dapodik/NPD)
   * `legacy_codes`: `ARRAY['...']` (Daftar kode lama sebelum pemekaran provinsi/kabupaten)

---

## 5. Pipeline Pemrosesan Geometri Batas Wilayah (BIG $\rightarrow$ Peta 3D WebGL)

1. **Akuisisi Sumber:** Mengambil layer *Batas Wilayah Administrasi Kabupaten/Kota* resmi dari BIG (`tanahair.indonesia.go.id`).
2. **Standarisasi Sistem Koordinat (CRS):**
   * Penyimpanan dan pengiriman API menggunakan **WGS 84 (`EPSG:4326`)** dengan pembulatan presisi koordinat hingga $6$ angka desimal ($\approx 11\text{ cm}$).
   * Perhitungan luas wilayah (`area_km2`) dilakukan menggunakan proyeksi *equal-area* / `ST_Area(geom::geography) / 1000000.0`.
3. **Simplifikasi Berbasis Topologi (Mencegah Celah Antar-Kabupaten):**
   * Dilarang menggunakan `ST_Simplify` per baris poligon secara terpisah karena akan menciptakan celah (*slivers*) atau tumpang tindih pada batas antar-kabupaten di peta 3D.
   * Gunakan `ST_CoverageSimplify` (PostGIS 3.4+) atau `mapshaper -simplify visvalingam 8% keep-shapes` sehingga batas bersama antar-kabupaten tetap terkunci rapat dan pulau-pulau kecil (`keep-shapes`) tidak hilang:
     * **Resolusi `low` (Overview Nasional 3D):** Format **TopoJSON** berisi seluruh 514 Kabupaten/Kota dengan ukuran terkompresi $< 1,8\text{ MB}$.
     * **Resolusi `high` (Drill-down Provinsi/Kabupaten):** Format GeoJSON detail per provinsi atau kabupaten.
4. **Titik Jangkar Kamera & Label 3D (`anchor_point`):**
   * Dihitung menggunakan `ST_PointOnSurface(geom)` (bukan `ST_Centroid`), sehingga titik label dan target kamera *fly-to* dijamin selalu berada di atas daratan utama meskipun wilayah tersebut berbentuk kepulauan (seperti Kab. Kepulauan Seribu, Kab. Maluku Tenggara, atau Kab. Raja Ampat).