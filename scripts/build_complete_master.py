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

def build_complete_master():
    print("Compiling complete verified indicators master...")
    
    # 1. Base BPS Core
    bps_rows = []
    with open("data/bps_verified_indicators.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            bps_rows.append(r)
    print(f"Loaded {len(bps_rows)} base regions from BPS.")
    
    # 2. BNPB Multi-Hazard
    irbi_map = {}
    with open("data/irbi_2024_multihazard.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            irbi_map[norm(r["region_name"])] = r
            
    # 3. BNPB Specific Hazards (Banjir, Gempa, Longsor)
    hazards_map = {}
    with open("data/bnpb_irbi_specific_hazards_2024.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            hazards_map[norm(r["region_name"])] = r
            
    # 4. Kemenkes SKI Stunting
    ski_map = {}
    with open("data/kemenkes_ski_2023_stunting.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["is_provincial_total"] != "True":
                ski_map[norm(r["region_name"])] = r
                
    # 5. BPS Sanitasi Kab/Kota (SDGs 2025)
    sanitasi_map = {}
    with open("data/bps_sanitasi_kabkota_2025.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            sanitasi_map[r["bps_code"]] = r["inf_safe_sanitation_pct"]
            
    # 6. BPS Provincial SDGs (Air Minum & Listrik)
    prov_sdgs_map = {}
    with open("data/bps_provincial_sdgs_2025.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            prov_sdgs_map[r["bps_prov_code"][:2]] = r # match 2-digit prov prefix
            
    # 7. Kemendikdasmen Schools 2026
    schools_map = {}
    with open("data/kemendikdasmen_schools_kabkota.csv", "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            schools_map[norm(r["region_name"])] = r

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

    master = []
    for r in bps_rows:
        code = r["bps_code"]
        name = r["region_name"]
        k = norm(name)
        lk = aliases.get(k, k)
        prov_prefix = code[:2]
        
        # Helper finder
        def find_in(d):
            m = d.get(lk) or d.get(k)
            if not m:
                for p in name.split("/"):
                    pk = norm(p)
                    if pk in d:
                        return d[pk]
            return m

        # BNPB Multi
        irbi_m = find_in(irbi_map)
        r["dis_multihazard_index"] = irbi_m["dis_multihazard_index"] if irbi_m else ""
        r["dis_risk_class"] = irbi_m["risk_class"] if irbi_m else ""
        
        # BNPB Specific
        haz_m = find_in(hazards_map)
        r["dis_flood_score"] = haz_m["dis_flood_score"] if haz_m else ""
        r["dis_flood_class"] = haz_m["dis_flood_class"] if haz_m else ""
        r["dis_earthquake_score"] = haz_m["dis_earthquake_score"] if haz_m else ""
        r["dis_earthquake_class"] = haz_m["dis_earthquake_class"] if haz_m else ""
        r["dis_landslide_score"] = haz_m["dis_landslide_score"] if haz_m else ""
        r["dis_landslide_class"] = haz_m["dis_landslide_class"] if haz_m else ""
        
        # SKI Stunting
        ski_m = find_in(ski_map)
        r["hlt_stunting_prevalence"] = ski_m["hlt_stunting_prevalence"] if ski_m and ski_m["hlt_stunting_prevalence"] else ""
        
        # BPS Sanitasi
        r["inf_safe_sanitation_pct"] = sanitasi_map.get(code, "")
        
        # BPS Prov SDGs (Air & Listrik)
        ps = prov_sdgs_map.get(prov_prefix)
        r["inf_safe_water_prov_pct"] = ps["inf_safe_water_prov_pct"] if ps else ""
        r["inf_electrification_prov_pct"] = ps["inf_electrification_prov_pct"] if ps else ""
        
        # Kemendikdasmen Schools
        sch_m = find_in(schools_map)
        r["edu_schools_sd"] = sch_m["edu_schools_sd"] if sch_m else ""
        r["edu_schools_smp"] = sch_m["edu_schools_smp"] if sch_m else ""
        r["edu_schools_sma"] = sch_m["edu_schools_sma"] if sch_m else ""
        r["edu_schools_smk"] = sch_m["edu_schools_smk"] if sch_m else ""
        r["edu_schools_total"] = sch_m["edu_schools_total"] if sch_m else ""
        
        master.append(r)
        
    out_csv = "data/verified_indicators_master.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        fields = list(master[0].keys())
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(master)
        
    print(f"\nFinal Complete Master saved to {out_csv} ({os.path.getsize(out_csv)} bytes)")
    print(f"Total Columns: {len(fields)}")
    print("Columns:", ", ".join(fields))

if __name__ == "__main__":
    build_complete_master()
