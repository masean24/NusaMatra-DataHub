import os
import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = os.getenv("BPS_API_KEY", "")

for vid in [87, 772]:
    url = f"https://webapi.bps.go.id/v1/api/list/model/th/domain/0000/var/{vid}/key/{API_KEY}/"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})) as r:
        d = json.loads(r.read().decode("utf-8"))
        years = d.get("data", [{}, []])[1]
        print(f"Var {vid} years:", [y.get("th") for y in years[:5]])
