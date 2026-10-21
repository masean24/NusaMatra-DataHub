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
        if data.get("data-availability") != "available":
            raise ValueError(f"Data not available for var {var_id}")
        return data

def parse_var_content(data, var_id, th_id):
    datacontent = data.get("datacontent", {})
    vervar_lookup = {v["val"]: v["label"] for v in data.get("vervar", [])}
    
    res = {}
    for k, val in datacontent.items():
        k_str = str(k)
        if val is None:
            continue
        # Find matching vervar
        for vid, vlabel in vervar_lookup.items():
            if k_str.startswith(str(vid)):
                res[vid] = (vlabel, float(val))
                break
    return res

def main():
    print("Fetching P1 (var 622), P2 (var 623), and Garis Kemiskinan (var 624) for 2025...")
    d_p1 = fetch_var(622, 125)
    d_p2 = fetch_var(623, 125)
    d_gk = fetch_var(624, 125)
    
    p1_data = parse_var_content(d_p1, 622, 125)
    p2_data = parse_var_content(d_p2, 623, 125)
    gk_data = parse_var_content(d_gk, 624, 125)
    
    print(f"Parsed P1: {len(p1_data)}, P2: {len(p2_data)}, GK: {len(gk_data)}")
    
    # Read existing bps_verified_indicators.csv
    in_csv = "data/bps_verified_indicators.csv"
    with open(in_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    new_fields = ["soc_poverty_gap_p1", "soc_poverty_severity_p2", "soc_poverty_line"]
    for nf in new_fields:
        if nf not in fieldnames:
            fieldnames.append(nf)
            
    for row in rows:
        code_int = int(row["bps_code"]) if row["bps_code"].isdigit() else None
        if code_int:
            if code_int in p1_data:
                row["soc_poverty_gap_p1"] = p1_data[code_int][1]
            if code_int in p2_data:
                row["soc_poverty_severity_p2"] = p2_data[code_int][1]
            if code_int in gk_data:
                row["soc_poverty_line"] = gk_data[code_int][1]
                
    with open(in_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Updated {in_csv} with P1, P2, and Garis Kemiskinan!")

if __name__ == "__main__":
    main()
