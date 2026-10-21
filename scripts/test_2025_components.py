import os
import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = os.getenv("BPS_API_KEY", "")

for vid in [415, 416, 417]:
    url = f"https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/{vid}/th/125/key/{API_KEY}/"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})) as resp:
        d = json.loads(resp.read().decode("utf-8"))
        print(f"Var {vid} 2025 status: {d.get('data-availability')}, items: {len(d.get('datacontent', {}))}")
