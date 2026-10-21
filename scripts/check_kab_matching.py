import sqlite3
import csv

conn = sqlite3.connect('data/nusa_matra_live.db')
c = conn.cursor()
c.execute('SELECT region_id, name, bps_code, kemendagri_code FROM dim_regions WHERE level != "provinsi"')
db_kabs = c.fetchall()

print(f"Total db kab/kota: {len(db_kabs)}")
print("Sample db kab:", db_kabs[:5])

# Check master
with open('data/verified_indicators_master.csv', 'r', encoding='utf-8') as f:
    master = list(csv.DictReader(f))

# Match by bps_code or region_id or name
bps_to_regid = {}
for r_id, name, bps, kd in db_kabs:
    bps_to_regid[bps] = r_id
    bps_to_regid[r_id] = r_id

matched = sum(1 for m in master if m['bps_code'] in bps_to_regid)
print(f"Matched by code directly: {matched} / {len(master)}")
