import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
with open('data/raw/bps/all_bps_variables.json', 'r', encoding='utf-8') as f:
    vars_list = json.load(f)

for v in vars_list:
    vid = v.get("var_id")
    if vid and 2730 <= vid <= 2760:
        print(f"Var {vid}: [{v.get('sub_name')}] {v.get('title')}")
