import csv
import re
import os

def norm(s):
    if not s:
        return ""
    s = s.upper()
    s = s.replace("KABUPATEN", "").replace("KAB.", "").replace("KOTA", "")
    s = s.replace("ADM.", "").replace("ADMINISTRASI", "")
    s = re.sub(r'[^A-Z0-9]', '', s)
    return s

def build_master():
    print("Building unified verified master dataset...")
    
    # 1. Load BPS Indicators (541 regions including prov/national, 514+ kab)
    bps_rows = []
    with open("data/bps_verified_indicators.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        bps_fields = reader.fieldnames
        for r in reader:
            bps_rows.append(r)
    print(f"Loaded {len(bps_rows)} rows from BPS.")
    
    # 2. Load BNPB IRBI 2024
    irbi_map = {}
    with open("data/irbi_2024_multihazard.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = norm(r["region_name"])
            irbi_map[k] = r
    print(f"Loaded {len(irbi_map)} normalized regions from BNPB IRBI.")
    
    # 3. Load Kemenkes SKI 2023 Stunting
    ski_map = {}
    with open("data/kemenkes_ski_2023_stunting.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["is_provincial_total"] == "True":
                continue
            k = norm(r["region_name"])
            ski_map[k] = r
    print(f"Loaded {len(ski_map)} normalized regions from Kemenkes SKI.")
    
    # Match & Merge
    master_rows = []
    irbi_matched = 0
    ski_matched = 0
    
    # Regional aliases for common spelling variations
    aliases = {
        "KOTAPADANGSIDIMPUAN": "PADANGSIDEMPUAN",
        "KEPSERIBU": "KEPULAUANSERIBU",
        "SIAUTAGULANDANGBIARO": "SITARO",
        "KOTAMAKASAR": "MAKASSAR",
        "TOBASAMOSIRTOBA": "TOBA",
        "TOBASAMOSIR": "TOBA",
        "LABUHANBATU": "LABUHANBATU",
        "BATANGHARI": "BATANGHARI",
        "BANYUASIN": "BANYUASIN"
    }
    
    for row in bps_rows:
        code = row["bps_code"]
        name = row["region_name"]
        clean_k = norm(name)
        
        # Check aliases
        lookup_k = aliases.get(clean_k, clean_k)
        
        # Match IRBI
        irbi_match = irbi_map.get(lookup_k) or irbi_map.get(clean_k)
        if not irbi_match:
            # try matching without slash
            for p in name.split("/"):
                pk = norm(p)
                if pk in irbi_map:
                    irbi_match = irbi_map[pk]
                    break
                    
        if irbi_match:
            row["dis_multihazard_index"] = irbi_match["dis_multihazard_index"]
            row["dis_risk_class"] = irbi_match["risk_class"]
            irbi_matched += 1
        else:
            row["dis_multihazard_index"] = ""
            row["dis_risk_class"] = ""
            
        # Match SKI Stunting
        ski_match = ski_map.get(lookup_k) or ski_map.get(clean_k)
        if not ski_match:
            for p in name.split("/"):
                pk = norm(p)
                if pk in ski_map:
                    ski_match = ski_map[pk]
                    break
                    
        if ski_match and ski_match["hlt_stunting_prevalence"]:
            row["hlt_stunting_prevalence"] = ski_match["hlt_stunting_prevalence"]
            ski_matched += 1
        else:
            row["hlt_stunting_prevalence"] = ""
            
        master_rows.append(row)
        
    print(f"\nMerge Results across {len(master_rows)} regions:")
    print(f"- IRBI Multi-Hazard matched: {irbi_matched}")
    print(f"- SKI Stunting matched: {ski_matched}")
    
    out_fields = list(bps_fields) + ["dis_multihazard_index", "dis_risk_class", "hlt_stunting_prevalence"]
    out_csv = "data/verified_indicators_master.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(master_rows)
        
    print(f"Master file saved to {out_csv} ({os.path.getsize(out_csv)} bytes)")

if __name__ == "__main__":
    build_master()
