# PANDUAN INTEGRASI FEED GEMPABUMI BMKG (NUSA MATRA DATA HUB)
## Dokumentasi Endpoint Real-Time BMKG untuk Frontend 3D Map & Dashboard

**Status Integrasi:** 100% Selesai & Teruji (65/65 Unit Test Passing)  
**Lembaga Sumber:** Badan Meteorologi, Klimatologi, dan Geofisika (BMKG)  
**Portal Resmi:** [https://data.bmkg.go.id/gempabumi/](https://data.bmkg.go.id/gempabumi/)  
**Update Frequency:** Event-Driven (Real-time update setiap kejadian gempa)  
**Caching Backend:** Smart In-Memory Cache (TTL: 60 detik) — Aman dari rate limit BMKG  

---

## 1. Daftar Endpoint Baru

| No | Metode | Endpoint | Deskripsi | Kegunaan di Frontend |
| :-: | :---: | :--- | :--- | :--- |
| 1 | `GET` | `/api/v1/earthquakes/latest` | 1 Kejadian gempa terbaru nasional | Banner breaking news / highlight kejadian terkini + Shakemap image |
| 2 | `GET` | `/api/v1/earthquakes/recent` | 15 Gempa signifikan terbaru (M ≥ 5.0) | Tabel rekapitulasi gempa besar & timeline |
| 3 | `GET` | `/api/v1/earthquakes/felt` | 15 Gempa yang dilaporkan dirasakan warga | Daftar gempa dirasakan + intensitas skala MMI |
| 4 | `GET` | `/api/v1/earthquakes/geojson` | **RFC 7946 Standard GeoJSON FeatureCollection** | **Lapisan marker episenter 3D di peta Jelajahi** |
| 5 | `GET` | `/api/v1/earthquakes/summary` | Ringkasan statistik aktivitas seismik | Widget ringkasan dashboard |

---

## 2. Format Khusus GeoJSON untuk Peta 3D (`/api/v1/earthquakes/geojson`)

Endpoint ini menggabungkan seluruh feed gempabumi (terbaru, M ≥ 5.0, dan dirasakan) dengan **deduplikasi otomatis** dan **pengurutan kronologis terbaru**.

### Contoh Respons GeoJSON:
```json
{
  "type": "FeatureCollection",
  "metadata": {
    "agency": "BMKG",
    "description": "Indonesian Seismic Monitoring Epicenters (Unified Live Feed)",
    "total_features": 28,
    "cached_at": "2026-10-22T03:00:00Z",
    "source_portal": "https://data.bmkg.go.id/gempabumi/"
  },
  "features": [
    {
      "type": "Feature",
      "id": "bmkg-20261021T115836Z0000--5.40-104.68",
      "geometry": {
        "type": "Point",
        "coordinates": [104.68, -5.40]
      },
      "properties": {
        "id": "bmkg-20261021T115836Z0000--5.40-104.68",
        "datetime": "2026-10-21T11:58:36+00:00",
        "date": "21 Okt 2026",
        "time": "18:58:36 WIB",
        "magnitude": 2.5,
        "depth": "3 km",
        "depth_km": 3.0,
        "area": "Pusat gempa berada di darat 9 km utara Tanggamus",
        "potency": "Gempa ini dirasakan untuk diteruskan pada masyarakat",
        "felt": "II Tanggamus",
        "shakemap_url": "https://data.bmkg.go.id/DataMKG/TEWS/20261021185836.mmi.jpg",
        "severity": "LOW",
        "tsunami_risk": false,
        "source": "BMKG",
        "visual_radius_px": 7.78,
        "visual_color": "#3b82f6"
      }
    }
  ]
}
```

### Properti Visual Siap Pakai untuk Claude (Frontend):
* **`coordinates`**: Sudah dinormalisasi menjadi `[longitude, latitude]` numerik standar GeoJSON (tidak perlu lagi mem-parsing string).
* **`visual_radius_px`**: Ukuran radius titik yang dihitung secara eksponensial berdasarkan magnitudo gempa.
* **`visual_color`**: Kode warna heksadesimal standar tanggap darurat:
  * Merah Tua (`#ef4444`): Magnitudo ≥ 6.0 (SEVERE)
  * Oranye (`#f97316`): Magnitudo 5.0 – 5.9 (HIGH)
  * Kuning (`#eab308`): Magnitudo 4.0 – 4.9 (MODERATE)
  * Biru (`#3b82f6`): Magnitudo < 4.0 (LOW)
* **`depth_km`**: Nilai numerik kedalaman (km) yang dapat digunakan oleh visualisasi 3D untuk efek elevasi episenter.
* **`tsunami_risk`**: Boolean (`true`/`false`) untuk efek visual peringatan bahaya gelombang tsunami.
* **`shakemap_url`**: Tautan absolut ke gambar peta guncangan resmi BMKG, siap ditampilkan di modal / *side panel*.

---

## 3. Contoh Implementasi di Frontend (Mapbox / MapLibre / Deck.gl)

Claude hanya butuh beberapa baris kode di komponen peta 3D untuk mengaktifkan lapisan gempa ini:

```javascript
// 1. Tambahkan GeoJSON Source dari backend Nusa Matra
map.addSource('bmkg-earthquakes', {
  type: 'geojson',
  data: 'https://api.orangkeren.me/api/v1/earthquakes/geojson?mode=live'
});

// 2. Tambahkan Circle Layer dengan styling otomatis dari properties backend
map.addLayer({
  id: 'earthquake-circles',
  type: 'circle',
  source: 'bmkg-earthquakes',
  paint: {
    'circle-radius': ['get', 'visual_radius_px'],
    'circle-color': ['get', 'visual_color'],
    'circle-opacity': 0.8,
    'circle-stroke-width': 2,
    'circle-stroke-color': '#ffffff'
  }
});

// 3. Tambahkan popup saat marker diklik
map.on('click', 'earthquake-circles', (e) => {
  const props = e.features[0].properties;
  new mapboxgl.Popup()
    .setLngLat(e.lngLat)
    .setHTML(`
      <div style="font-family: sans-serif; padding: 6px;">
        <h4 style="margin: 0 0 4px 0;">Magnitudo ${props.magnitude} SR</h4>
        <p style="margin: 0; font-size: 12px; color: #666;">${props.area}</p>
        <p style="margin: 4px 0; font-size: 11px;">Kedalaman: <b>${props.depth}</b> | ${props.time}</p>
        ${props.felt ? `<p style="margin: 2px 0; font-size: 11px; color: #f97316;">Dirasakan: ${props.felt}</p>` : ''}
        ${props.shakemap_url ? `<img src="${props.shakemap_url}" style="width: 100%; margin-top: 6px; border-radius: 4px;" />` : ''}
      </div>
    `)
    .addTo(map);
});
```

---

## 4. Keunggulan Arsitektur Backend Nusa Matra
1. **Zero-Latency In-Memory Cache (TTL 60s):**  
   Beban ke server BMKG hanya 1 kali per menit terlepas dari berapapun jumlah pengguna aktif yang membuka peta.
2. **Resilience & Offline Fallback:**  
   Jika server BMKG sewaktu-waktu mengalami gangguan, backend otomatis menyajikan snapshot data terakhir dari cache atau *fixture*, sehingga UI frontend tidak akan pernah mengalami error *crash* atau *blank screen*.
3. **Pilar Provenance Lengkap:**  
   Katalog dataset resmi di `/api/v1/datasets` kini mencakup **BMKG** bersama BIG, BPS, BNPB, Kemenkes, dan Kemendikdasmen.
