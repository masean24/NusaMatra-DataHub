import os
import urllib.request
import json
import csv
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = os.getenv("BPS_API_KEY", "")

url = f"https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/2748/th/125/key/{API_KEY}/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15) as r:
    data = json.loads(r.read().decode("utf-8"))

datacontent = data.get("datacontent", {})
vervar_lookup = {v["val"]: v["label"] for v in data.get("vervar", [])}

sanitasi_rows = []
for k, val in datacontent.items():
    k_str = str(k)
    if val is None:
        continue
    for vid, vlabel in vervar_lookup.items():
        if k_str.startswith(str(vid)):
            sanitasi_rows.append({
                "bps_code": str(vid),
                "region_name": vlabel,
                "inf_safe_sanitation_pct": float(val),
                "year": 2025,
                "source": "BPS Susenas SDGs 2025"
            })
            break

print(f"Extracted {len(sanitasi_rows)} kabupaten/kota for Sanitasi Layak (SDGs 6.2.1):")
for r in sanitasi_rows[:10]:
    print(" ", r["bps_code"], r["region_name"], "->", r["inf_safe_sanitation_pct"], "%")

with open("data/bps_sanitasi_kabkota_2025.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["bps_code", "region_name", "inf_safe_sanitation_pct", "year", "source"])
    writer.writeheader()
    writer.writerows(sanitasi_rows)
print("Saved to data/bps_sanitasi_kabkota_2025.csv")
