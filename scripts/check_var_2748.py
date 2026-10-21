import os
import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = os.getenv("BPS_API_KEY", "")

url = f"https://webapi.bps.go.id/v1/api/list/model/th/domain/0000/var/2748/key/{API_KEY}/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    years = data.get("data", [{}, []])[1]
    print("Var 2748 years:", years)

# check data for latest year
if years:
    latest_th = years[0].get("th_id")
    url_data = f"https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/2748/th/{latest_th}/key/{API_KEY}/"
    with urllib.request.urlopen(urllib.request.Request(url_data, headers={"User-Agent": "Mozilla/5.0"})) as r:
        d = json.loads(r.read().decode("utf-8"))
        print(f"Var 2748 (th {latest_th}) status: {d.get('data-availability')}, items: {len(d.get('datacontent', {}))}")
