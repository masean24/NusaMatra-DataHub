import os
import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = os.getenv("BPS_API_KEY", "")

url = f"https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/845/th/125/key/{API_KEY}/"
with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})) as r:
    d = json.loads(r.read().decode("utf-8"))
    print(f"Var 845 2025 status: {d.get('data-availability')}")
    print(f"Vervar count: {len(d.get('vervar', []))}")
    print(f"Datacontent count: {len(d.get('datacontent', {}))}")
    for v in d.get('vervar', [])[:5]:
        print("  Sample vervar:", v)
