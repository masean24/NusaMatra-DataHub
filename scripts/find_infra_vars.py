import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
with open('data/raw/bps/all_bps_variables.json', 'r', encoding='utf-8') as f:
    vars_list = json.load(f)

for v in vars_list:
    t = v.get('title', '').lower()
    sub = v.get('sub_name', '').lower()
    if any(k in t for k in ['sanitasi', 'air minum', 'air bersih', 'listrik', 'penerangan', 'sampah', 'jamban']):
        print(f"{v.get('var_id')}: [{sub}] {v.get('title')}")
