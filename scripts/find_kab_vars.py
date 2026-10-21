import json
import sys

# ensure utf-8 stdout
sys.stdout.reconfigure(encoding='utf-8')

with open('data/raw/bps/all_bps_variables.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find variables that are relevant to our indicators (Pendidikan, Kemiskinan, IPM, Kesehatan, Sanitasi, Perumahan, Ketenagakerjaan)
targets = ["kemiskinan", "indeks pembangunan manusia", "kesehatan", "pendidikan", "perumahan", "tenaga kerja", "komunikasi", "sosial budaya", "gender", "pemerintahan"]

for v in data:
    sub = (v.get("sub_name") or "").lower()
    title = (v.get("title") or "").lower()
    if any(t in sub for t in targets):
        if "kabupaten" in title or "kabupaten" in (v.get("notes") or "").lower() or v.get("var_id") in [413, 414, 415, 416, 417, 619, 621, 622, 623, 624, 2824, 1950, 845, 847, 304]:
            print(f"ID: {v.get('var_id')} | Sub: {v.get('sub_name')} | Title: {v.get('title')}")
