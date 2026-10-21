import os
import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
API_KEY = os.getenv("BPS_API_KEY", "")

# Test if any var has 2026
for vid in [413, 621, 2824]:
    url = f"https://webapi.bps.go.id/v1/api/list/model/th/domain/0000/var/{vid}/key/{API_KEY}/"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})) as resp:
        d = json.loads(resp.read().decode("utf-8"))
        years = [y.get("th") for y in d.get("data", [{}, []])[1]]
        print(f"Var {vid}: all years -> {years[:10]}")
