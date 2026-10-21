import csv

# Load BPS
bps_data = {}
with open("data/bps_verified_indicators.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        bps_data[row["bps_code"]] = row["region_name"].upper().strip()

# Load BNPB
irbi_data = {}
with open("data/irbi_2024_multihazard.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        name = row["region_name"].upper().strip()
        # normalize common prefixes
        clean = name.replace("KAB. ", "").replace("KOTA ", "").strip()
        irbi_data[clean] = row

matched = 0
unmatched = []
for code, name in bps_data.items():
    clean = name.replace("KAB. ", "").replace("KOTA ", "").strip()
    if clean in irbi_data or name in irbi_data:
        matched += 1
    else:
        unmatched.append((code, name))

print(f"Total BPS regions: {len(bps_data)}")
print(f"Matched directly with BNPB IRBI: {matched}")
print(f"Unmatched: {len(unmatched)}")
if unmatched:
    print("Sample unmatched:", unmatched[:10])
