import urllib.request
import ssl
import sys
import re
import csv
import os
import time

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def fetch_page(p, retries=3):
    raw_path = f"data/raw/bnpb/irbi_page_{p}.html"
    if os.path.exists(raw_path):
        with open(raw_path, "r", encoding="utf-8") as f:
            return f.read()
    url = f"https://inarisk.bnpb.go.id/IRBI-2024/files/basic-html/page{p}.html"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
                html = r.read().decode('utf-8', errors='ignore')
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(html)
                return html
        except Exception as e:
            if attempt == retries - 1:
                print(f"Error fetching page {p}: {e}")
                return ""
            time.sleep(1.0)
    return ""

def clean_name(s):
    s = s.strip()
    if s == "P A P U A":
        return "PAPUA"
    return " ".join(s.split())

def parse_hazard_table(start_p, end_p, hazard_name):
    print(f"\n--- Parsing {hazard_name} (pages {start_p} to {end_p}) ---")
    data = {}
    for p in range(start_p, end_p + 1):
        html = fetch_page(p)
        if not html:
            continue
        text = re.sub(r'<[^>]+>', '\n', html)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        page_count = 0
        for line in lines:
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 5 and parts[0].isdigit():
                try:
                    rank = int(parts[0])
                    kab = clean_name(parts[1])
                    prov = clean_name(parts[2])
                    score = float(parts[3])
                    kelas = parts[4].strip()
                    key = f"{prov}|{kab}"
                    data[key] = {
                        "rank": rank,
                        "province_name": prov,
                        "region_name": kab,
                        "score": score,
                        "class": kelas
                    }
                    page_count += 1
                except (ValueError, IndexError):
                    continue
        time.sleep(0.1)
    print(f"Total extracted for {hazard_name}: {len(data)} regions")
    return data

def main():
    os.makedirs("data/raw/bnpb", exist_ok=True)
    banjir = parse_hazard_table(212, 225, "Banjir")
    gempa = parse_hazard_table(226, 243, "Gempabumi")
    longsor = parse_hazard_table(278, 295, "Tanah Longsor")
    
    # Save combined hazard CSV
    all_keys = set(banjir.keys()) | set(gempa.keys()) | set(longsor.keys())
    print(f"\nTotal unique regions across all 3 hazards: {len(all_keys)}")
    
    rows = []
    for k in sorted(all_keys):
        prov, kab = k.split("|")
        b = banjir.get(k, {})
        g = gempa.get(k, {})
        l = longsor.get(k, {})
        rows.append({
            "province_name": prov,
            "region_name": kab,
            "dis_flood_score": b.get("score", ""),
            "dis_flood_class": b.get("class", ""),
            "dis_earthquake_score": g.get("score", ""),
            "dis_earthquake_class": g.get("class", ""),
            "dis_landslide_score": l.get("score", ""),
            "dis_landslide_class": l.get("class", ""),
            "source": "BNPB IRBI 2024"
        })
        
    out_csv = "data/bnpb_irbi_specific_hazards_2024.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        fields = [
            "province_name", "region_name",
            "dis_flood_score", "dis_flood_class",
            "dis_earthquake_score", "dis_earthquake_class",
            "dis_landslide_score", "dis_landslide_class",
            "source"
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} regions to {out_csv}!")

if __name__ == "__main__":
    main()
