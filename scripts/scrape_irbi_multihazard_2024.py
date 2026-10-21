import urllib.request
import ssl
import sys
import re
import csv
import os

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def clean_name(s):
    # Handle spaced letters like "P A P U A"
    s = s.strip()
    if s == "P A P U A":
        return "PAPUA"
    return " ".join(s.split())

def scrape_multihazard():
    os.makedirs("data/raw/bnpb", exist_ok=True)
    all_rows = []
    
    print("Scraping IRBI 2024 Multi-Hazard table from pages 38 to 53...")
    for p in range(38, 54):
        url = f"https://inarisk.bnpb.go.id/IRBI-2024/files/basic-html/page{p}.html"
        raw_path = f"data/raw/bnpb/irbi_page_{p}.html"
        
        if os.path.exists(raw_path):
            with open(raw_path, "r", encoding="utf-8") as f:
                html = f.read()
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                html = r.read().decode('utf-8', errors='ignore')
            with open(raw_path, "w", encoding="utf-8") as f:
                f.write(html)
        
        text = re.sub(r'<[^>]+>', '\n', html)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        page_rows = 0
        for line in lines:
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 5 and parts[0].isdigit():
                rank = int(parts[0])
                kab = clean_name(parts[1])
                prov = clean_name(parts[2])
                try:
                    score = float(parts[3])
                except ValueError:
                    continue
                kelas = parts[4].strip()
                
                all_rows.append({
                    "rank": rank,
                    "region_name": kab,
                    "province_name": prov,
                    "dis_multihazard_index": score,
                    "risk_class": kelas,
                    "reference_year": 2024,
                    "source": "BNPB IRBI 2024"
                })
                page_rows += 1
        print(f"Page {p}: extracted {page_rows} rows")
    
    # Sort by rank
    all_rows.sort(key=lambda x: x["rank"])
    print(f"\nTotal extracted rows: {len(all_rows)}")
    
    out_csv = "data/irbi_2024_multihazard.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "region_name", "province_name", "dis_multihazard_index", "risk_class", "reference_year", "source"])
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Saved to {out_csv}")
    
    # Verification stats
    print("Summary:")
    print("Min rank:", min(r["rank"] for r in all_rows), "Max rank:", max(r["rank"] for r in all_rows))
    print("Min score:", min(r["dis_multihazard_index"] for r in all_rows), "Max score:", max(r["dis_multihazard_index"] for r in all_rows))

if __name__ == "__main__":
    scrape_multihazard()
