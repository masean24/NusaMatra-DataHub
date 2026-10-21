import urllib.request
import json
import os
import concurrent.futures

BPS_API_KEY = os.getenv("BPS_API_KEY", "")
OUT_FILE = "data/raw/bps/all_bps_variables.json"

def fetch_page(page):
    url = f"https://webapi.bps.go.id/v1/api/list/model/var/domain/0000/key/{BPS_API_KEY}/page/{page}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("data-availability") == "available":
                return data["data"][1]
    except Exception as e:
        print(f"Error page {page}: {e}")
    return []

def main():
    os.makedirs("data/raw/bps", exist_ok=True)
    if os.path.exists(OUT_FILE):
        print(f"Already have {OUT_FILE}")
        with open(OUT_FILE, "r", encoding="utf-8") as f:
            all_vars = json.load(f)
    else:
        print("Fetching all 176 pages of BPS variables...")
        all_vars = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_page = {executor.submit(fetch_page, p): p for p in range(1, 177)}
            for future in concurrent.futures.as_completed(future_to_page):
                res = future.result()
                all_vars.extend(res)
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_vars, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(all_vars)} variables to {OUT_FILE}")

    # Search keywords
    keywords = ["sanitasi", "air minum", "air bersih", "stunting", "partisipasi murni", "apm", "listrik", "penerangan", "internet", "sekolah", "kesehatan", "puskesmas", "rumah sakit", "bencana"]
    print("\n--- Search Results ---")
    for kw in keywords:
        matches = [v for v in all_vars if kw in v.get("title", "").lower()]
        print(f"\nKeyword '{kw}': {len(matches)} matches")
        for m in matches[:5]:
            print(f"  [ID {m.get('var_id')}] (sub: {m.get('sub_name')}) {m.get('title')}")

if __name__ == "__main__":
    main()
