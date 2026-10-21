import csv
import re

def norm(s):
    s = s.upper()
    s = s.replace("KABUPATEN", "").replace("KAB.", "").replace("KOTA", "")
    s = s.replace("ADM.", "").replace("ADMINISTRASI", "")
    s = re.sub(r'[^A-Z0-9]', '', s)
    return s

# Load BNPB
irbi_norm = {}
with open("data/irbi_2024_multihazard.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        k = norm(row["region_name"])
        irbi_norm[k] = row

# Load BPS
bps_data = {}
with open("data/bps_verified_indicators.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        bps_data[row["bps_code"]] = row["region_name"]

matched = 0
unmatched = []
for code, name in bps_data.items():
    # If name has slash like "TOBA SAMOSIR / TOBA", test both
    parts = name.split("/")
    found = None
    for p in parts:
        k = norm(p)
        if k in irbi_norm:
            found = irbi_norm[k]
            break
    if found:
        matched += 1
    else:
        unmatched.append((code, name))

print(f"Total BPS: {len(bps_data)}, Matched: {matched}, Unmatched: {len(unmatched)}")
if unmatched:
    print("Unmatched:", unmatched)
