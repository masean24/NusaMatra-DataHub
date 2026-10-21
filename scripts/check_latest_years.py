import os
import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.getenv("BPS_API_KEY", "")
vars_to_check = {
    413: "IPM (HDI)",
    414: "UHH (Life Exp)",
    415: "RLS (Mean Schooling)",
    416: "Pengeluaran Riil",
    417: "HLS (Expected Schooling)",
    621: "Persentase Kemiskinan P0",
    619: "Jumlah Penduduk Miskin",
    622: "Kedalaman Kemiskinan P1",
    623: "Keparahan Kemiskinan P2",
    624: "Garis Kemiskinan",
    2824: "Tingkat Pengangguran Terbuka (TPT)"
}

for vid, label in vars_to_check.items():
    url = f"https://webapi.bps.go.id/v1/api/list/model/th/domain/0000/var/{vid}/key/{API_KEY}/"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            years = data.get("data", [{}, []])[1]
            th_list = [(y.get("th_id"), y.get("th")) for y in years[:5]]
            print(f"Var {vid} ({label}): {th_list}")
    except Exception as e:
        print(f"Var {vid} ({label}): Error {e}")
