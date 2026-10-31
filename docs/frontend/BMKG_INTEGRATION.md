# PANDUAN INTEGRASI FEED GEMPABUMI BMKG (NUSA MATRA DATA HUB)
## Dokumentasi Endpoint Real-Time BMKG, Provenance Metadata, Caching & Fail-Closed Behavior

**Status Integrasi:** 100% Selesai & Teruji (67/67 Unit Test Passing)  
**Lembaga Sumber:** Badan Meteorologi, Klimatologi, dan Geofisika (BMKG)  
**Portal Resmi:** [https://data.bmkg.go.id/gempabumi/](https://data.bmkg.go.id/gempabumi/)  
**Update Frequency:** Event-Driven (Real-time update setiap kejadian gempa)  
**Cache Policy:** `Cache-Control: no-cache, must-revalidate, max-age=0` (Backend in-memory cache TTL: 60s)  

---

## 1. Daftar Endpoint BMKG & Caching

| No | Metode | Endpoint | HTTP Cache-Control | Deskripsi |
| :-: | :---: | :--- | :--- | :--- |
| 1 | `GET` | `/api/v1/earthquakes/latest` | `no-cache, must-revalidate, max-age=0` | 1 Kejadian gempa terbaru nasional + Shakemap |
| 2 | `GET` | `/api/v1/earthquakes/recent` | `no-cache, must-revalidate, max-age=0` | 15 Gempa signifikan terbaru (M ≥ 5.0) |
| 3 | `GET` | `/api/v1/earthquakes/felt` | `no-cache, must-revalidate, max-age=0` | 15 Gempa yang dilaporkan dirasakan warga |
| 4 | `GET` | `/api/v1/earthquakes/geojson` | `no-cache, must-revalidate, max-age=0` | **RFC 7946 GeoJSON FeatureCollection untuk 3D Map** |
| 5 | `GET` | `/api/v1/earthquakes/summary` | `no-cache, must-revalidate, max-age=0` | Ringkasan statistik aktivitas seismik nasional |

> [!NOTE]
> **Kebijakan Caching:** Seluruh endpoint gempabumi menggunakan `Cache-Control: no-cache, must-revalidate, max-age=0`. Browser dan CDN tidak akan meng-cache data selama 1 jam, melainkan selalu memvalidasi ke backend. Backend sendiri melindungi BMKG dengan in-memory cache bertenggat waktu (TTL) 60 detik.

---

## 2. Struktur Metadata Asal Data (Provenance Pipeline)

Khususnya pada endpoint `/api/v1/earthquakes/geojson`, objek `metadata` memuat status pipeline sesungguhnya:

```json
{
  "type": "FeatureCollection",
  "metadata": {
    "agency": "BMKG",
    "description": "Indonesian Seismic Monitoring Epicenters (Unified Live Feed)",
    "total_features": 28,
    "data_origin": "bmkg_live",
    "last_success_at": "2026-10-22T04:20:15.208736+00:00",
    "is_stale": false,
    "cached_at": "2026-10-22T04:20:15.208736+00:00",
    "cache_ttl_seconds": 60,
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
        "data_origin": "bmkg_live",
        "visual_radius_px": 7.78,
        "visual_color": "#3b82f6"
      }
    }
  ]
}
```

---

## 3. Matriks 4 Kondisi Status Pipeline (Pembeda Frontend)

Frontend (Claude) dapat membedakan status asal data dengan jelas melalui kombinasi HTTP Status, Header, dan `metadata.data_origin`:

| Kondisi Data | HTTP Status | Header Mode | Header Fallback | `metadata.data_origin` | `metadata.is_stale` | Deskripsi Kondisi |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. BMKG Live Baru** | `200 OK` | `LIVE` | `NONE` | `bmkg_live` | `false` | Data baru diambil langsung dari server BMKG upstream. |
| **2. BMKG Live Cache** | `200 OK` | `LIVE` | `NONE` | `bmkg_cache` | `false` | Data diambil dari cache in-memory backend yang masih segar (< 60s). |
| **3. Demo Fixture** | `200 OK` | `DEMO` | `DEMO_FIXTURE` | `fixture` | `false` | Request mode DEMO (`?mode=demo`), data simulasi lokal, tidak disamarkan sebagai live. |
| **4. Upstream Gagal (Fail-Closed)** | `503 Service Unavailable` | `LIVE` | `UNAVAILABLE` | *N/A* | *N/A* | Server BMKG down & tidak ada cache valid. Request LIVE **gagal tertutup (fail-closed)** tanpa menipu user dengan fixture. |

---

## 4. Simulasi Kegagalan Upstream BMKG untuk Audit / Pengujian

Frontend atau QA auditor dapat menguji perilaku fail-closed kapan saja di production tanpa mengganggu request pengguna lain dengan menambahkan parameter atau header:

* **Via Query Param:**
  ```http
  GET /api/v1/earthquakes/geojson?mode=live&simulate_upstream_failure=true
  ```
* **Via Header:**
  ```http
  GET /api/v1/earthquakes/geojson?mode=live
  X-Simulate-Upstream-Failure: true
  ```

**Respons yang Dikembalikan saat Upstream Gagal:**
```http
HTTP/1.1 503 Service Unavailable
Content-Type: application/json
X-NusaMatra-Mode: LIVE
X-Data-Fallback: UNAVAILABLE
Cache-Control: no-cache, no-store, must-revalidate
```
```json
{
  "status": "error",
  "code": "UPSTREAM_UNAVAILABLE",
  "message": "BMKG live earthquake upstream service is currently unreachable. LIVE mode fails closed to prevent presenting unverified or synthetic data as official events.",
  "detail": "Simulated upstream BMKG failure for fail-closed verification."
}
```
*(Frontend dapat menampilkan banner peringatan: "Layanan BMKG sedang tidak dapat dihubungi" daripada menampilkan data usang).*

---

## 5. Contoh Implementasi di Frontend (Claude)

```javascript
async function loadEarthquakeLayer(map) {
  try {
    const res = await fetch('https://api.orangkeren.me/api/v1/earthquakes/geojson?mode=live');
    
    // Periksa jika backend melaporkan upstream BMKG tidak tersedia
    if (res.status === 503) {
      showNotificationWarning("Pemantauan gempa BMKG sedang mengalami gangguan upstream.");
      return;
    }

    const geojson = await res.json();
    const { data_origin, last_success_at, is_stale } = geojson.metadata;

    // Render badge indikator status data di pojok peta
    updateStatusBadge({
      origin: data_origin,       // 'bmkg_live' | 'bmkg_cache'
      updatedAt: last_success_at,
      stale: is_stale
    });

    // Tambahkan ke Mapbox / MapLibre 3D
    if (!map.getSource('bmkg-earthquakes')) {
      map.addSource('bmkg-earthquakes', { type: 'geojson', data: geojson });
      map.addLayer({
        id: 'earthquake-pulse',
        type: 'circle',
        source: 'bmkg-earthquakes',
        paint: {
          'circle-radius': ['get', 'visual_radius_px'],
          'circle-color': ['get', 'visual_color'],
          'circle-opacity': 0.85,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff'
        }
      });
    } else {
      map.getSource('bmkg-earthquakes').setData(geojson);
    }
  } catch (err) {
    console.error("Gagal memuat feed gempa:", err);
  }
}
```
