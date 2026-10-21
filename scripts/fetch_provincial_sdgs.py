import os
import urllib.request
import json
import csv
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = os.getenv("BPS_API_KEY", "")

def fetch_prov_var(var_id):
    url = f"https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/{var_id}/th/125/key/{API_KEY}/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    vervar = {v["val"]: v["label"] for v in data.get("vervar", [])}
    content = data.get("datacontent", {})
    
    res = {}
    for k, val in content.items():
        k_str = str(k)
        if val is None:
            continue
        for vid, vlabel in vervar.items():
            if k_str.startswith(str(vid)):
                res[vid] = (vlabel, float(val))
                break
    return res

def main():
    print("Fetching Provincial SDGs: Air Minum (845) & Listrik (772)...")
    air = fetch_prov_var(845)
    listrik = fetch_prov_var(772)
    
    all_vids = set(air.keys()) | set(listrik.keys())
    rows = []
    for vid in sorted(all_vids):
        prov_label = air.get(vid, (None, None))[0] or listrik.get(vid, (None, None))[0]
        air_val = air.get(vid, (None, None))[1]
        listrik_val = listrik.get(vid, (None, None))[1]
        rows.append({
            "bps_prov_code": vid,
            "province_name": prov_label,
            "inf_safe_water_prov_pct": air_val,
            "inf_electrification_prov_pct": listrik_val,
            "year": 2025,
            "source": "BPS Susenas 2025"
        })
        
    out_csv = "data/bps_provincial_sdgs_2025.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["bps_prov_code", "province_name", "inf_safe_water_prov_pct", "inf_electrification_prov_pct", "year", "source"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} provinces to {out_csv}!")

if __name__ == "__main__":
    main()
