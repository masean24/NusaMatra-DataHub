import asyncio
import json
import sys
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import httpx

async def run_smoke_test(base_url: str = None):
    endpoints_to_test = [
        ("GET", "/api/v1/health", {}),
        ("GET", "/api/v1/health?mode=live", {}),
        ("GET", "/api/v1/snapshots?mode=live", {}),
        ("GET", "/api/v1/datasets?mode=live", {}),
        ("GET", "/api/v1/regions?mode=live&level=provinsi", {}),
        ("GET", "/api/v1/regions/1101?mode=live", {}),
        ("GET", "/api/v1/indicators?mode=live", {}),
        ("GET", "/api/v1/indicators/soc_hdi/values?mode=live", {}),
        ("GET", "/api/v1/indicators/dis_multihazard_index/values?mode=live", {}),
        ("GET", "/api/v1/indicators/hlt_stunting_prevalence/values?mode=live", {}),
        ("POST", "/api/v1/indicators/composite-query?mode=live", {
            "weights": {
                "soc_hdi": 3000,
                "dis_multihazard_index": 3000,
                "soc_poverty_rate": 2000,
                "hlt_stunting_prevalence": 2000
            }
        }),
        ("GET", "/api/v1/earthquakes/latest?mode=live", {}),
        ("GET", "/api/v1/earthquakes/recent?mode=live", {}),
        ("GET", "/api/v1/earthquakes/felt?mode=live", {}),
        ("GET", "/api/v1/earthquakes/geojson?mode=live", {}),
        ("GET", "/api/v1/earthquakes/geojson?mode=demo", {}),
        ("GET", "/api/v1/earthquakes/geojson?mode=live&simulate_upstream_failure=true", {}),
        ("GET", "/api/v1/earthquakes/summary?mode=live", {})
    ]
    
    results = []

    if base_url:
        print(f"Connecting to remote target: {base_url}")
        async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
            for method, path, payload in endpoints_to_test:
                print(f"Testing {method} {path}...")
                if method == "GET":
                    resp = await client.get(path)
                else:
                    resp = await client.post(path, json=payload)
                
                headers_dict = {
                    "X-NusaMatra-Mode": resp.headers.get("X-NusaMatra-Mode"),
                    "X-NusaMatra-Snapshot": resp.headers.get("X-NusaMatra-Snapshot"),
                    "X-Data-Fallback": resp.headers.get("X-Data-Fallback"),
                    "Cache-Control": resp.headers.get("Cache-Control"),
                    "Content-Type": resp.headers.get("Content-Type")
                }
                
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                    
                results.append({
                    "method": method,
                    "endpoint": path,
                    "status_code": resp.status_code,
                    "headers": headers_dict,
                    "payload_sample": body
                })
    else:
        # Local in-process testing via ASGI
        from app.main import app
        from app.config import settings
        settings.enable_live_mode = True
        print("Running in-memory ASGI smoke test against local verified LIVE database...")

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for method, path, payload in endpoints_to_test:
                print(f"Testing {method} {path}...")
                if method == "GET":
                    resp = await client.get(path)
                else:
                    resp = await client.post(path, json=payload)
                    
                headers_dict = {
                    "X-NusaMatra-Mode": resp.headers.get("X-NusaMatra-Mode"),
                    "X-NusaMatra-Snapshot": resp.headers.get("X-NusaMatra-Snapshot"),
                    "X-Data-Fallback": resp.headers.get("X-Data-Fallback"),
                    "Cache-Control": resp.headers.get("Cache-Control"),
                    "Content-Type": resp.headers.get("Content-Type")
                }
                
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                    
                results.append({
                    "method": method,
                    "endpoint": path,
                    "status_code": resp.status_code,
                    "headers": headers_dict,
                    "payload_sample": body
                })

        settings.enable_live_mode = False

    output_file = "data/smoke_test_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print("\n" + "=" * 80)
    print(f"Smoke test complete! Results saved to {output_file}")
    print("=" * 80)
    for r in results:
        status_symbol = "[OK]" if r["status_code"] == 200 else f"[{r['status_code']}]"
        mode_val = r["headers"]["X-NusaMatra-Mode"]
        fallback_val = r["headers"]["X-Data-Fallback"]
        print(f"{status_symbol} {r['method']:<4} {r['endpoint']:<50} | Mode: {mode_val} | Fallback: {fallback_val}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke test Nusa Matra Data Hub endpoints")
    parser.add_argument("--base-url", type=str, default=None, help="Target remote base URL (e.g., https://api.orangkeren.me)")
    args = parser.parse_args()

    asyncio.run(run_smoke_test(base_url=args.base_url))
