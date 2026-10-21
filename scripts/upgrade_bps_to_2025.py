import urllib.request
import json
import csv
import os

API_KEY = os.getenv("BPS_API_KEY", "")

def fetch_var(var_id, th_id):
    url = f"https://webapi.bps.go.id/v1/api/list/model/data/domain/0000/var/{var_id}/th/{th_id}/key/{API_KEY}/"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data

def parse_var_content(data):
    datacontent = data.get("datacontent", {})
    vervar_lookup = {v["val"]: v["label"] for v in data.get("vervar", [])}
    
    res = {}
    for k, val in datacontent.items():
        k_str = str(k)
        if val is None:
            continue
        for vid, vlabel in vervar_lookup.items():
            if k_str.startswith(str(vid)):
                res[vid] = (vlabel, float(val))
                break
    return res

def update_to_2025():
    print("Updating RLS (415), Pengeluaran (416), and HLS (417) to 2025...")
    d_rls = fetch_var(415, 125)
    d_exp = fetch_var(416, 125)
    d_hls = fetch_var(417, 125)
    
    rls_2025 = parse_var_content(d_rls)
    exp_2025 = parse_var_content(d_exp)
    hls_2025 = parse_var_content(d_hls)
    
    print(f"Parsed 2025 data -> RLS: {len(rls_2025)}, Exp: {len(exp_2025)}, HLS: {len(hls_2025)}")
    
    in_csv = "data/bps_verified_indicators.csv"
    with open(in_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
        
    for r in rows:
        cid = int(r["bps_code"]) if r["bps_code"].isdigit() else None
        if cid:
            if cid in rls_2025:
                r["edu_mean_years_schooling"] = rls_2025[cid][1]
            if cid in exp_2025:
                r["soc_expenditure_per_capita"] = exp_2025[cid][1]
            if cid in hls_2025:
                r["edu_expected_years_schooling"] = hls_2025[cid][1]
                
    with open(in_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Successfully upgraded {in_csv} to 2025 data!")

if __name__ == "__main__":
    update_to_2025()
