import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
with open('data/smoke_test_results.json', 'r', encoding='utf-8') as f:
    res = json.load(f)

for item in res:
    print(f"=== {item['method']} {item['endpoint']} ===")
    print("Status:", item['status_code'])
    print("Headers:", item['headers'])
    body = item['payload_sample']
    if isinstance(body, dict):
        if 'data' in body:
            d = body['data']
            if isinstance(d, list):
                print(f"Data list length: {len(d)}, First item snippet:")
                print(json.dumps(d[0], indent=2)[:350])
            elif isinstance(d, dict):
                sample_snippet = json.dumps(d, indent=2)[:400]
                print(f"Data dict snippet: {sample_snippet}...")
    print("-" * 50)
