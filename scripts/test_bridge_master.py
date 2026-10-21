import sqlite3
import csv
import re

def norm(s):
    if not s:
        return ""
    s = s.upper()
    s = s.replace("KABUPATEN", "").replace("KAB.", "").replace("KOTA", "")
    s = s.replace("ADM.", "").replace("ADMINISTRASI", "")
    s = re.sub(r'[^A-Z0-9]', '', s)
    return s

conn = sqlite3.connect('data/nusa_matra_live.db')
c = conn.cursor()
c.execute('SELECT region_id, parent_region_id, name, bps_code, kemendagri_code FROM dim_regions WHERE level != "provinsi"')
db_kabs = c.fetchall()

db_name_map = {}
for r_id, p_id, name, bps, kd in db_kabs:
    k = norm(name)
    db_name_map[k] = r_id
    # also store with prov prefix
    db_name_map[f"{p_id}_{k}"] = r_id

with open('data/verified_indicators_master.csv', 'r', encoding='utf-8') as f:
    master = list(csv.DictReader(f))

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

matched = 0
unmatched = []
for m in master:
    name = m["region_name"]
    code = m["bps_code"]
    prov_id = code[:2]
    k = norm(name)
    lk = aliases.get(k, k)
    
    r_id = db_name_map.get(f"{prov_id}_{lk}") or db_name_map.get(lk) or db_name_map.get(f"{prov_id}_{k}") or db_name_map.get(k)
    if not r_id:
        for p in name.split("/"):
            pk = norm(p)
            if pk in db_name_map:
                r_id = db_name_map[pk]
                break
    if r_id:
        matched += 1
    else:
        unmatched.append((code, name))

print(f"Matched by name: {matched} / {len(master)}")
print(f"Unmatched: {len(unmatched)}")
if unmatched:
    print("Unmatched:", unmatched[:15])
