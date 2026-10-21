import urllib.request
import re
import ssl
import sys
import time
import csv
import os

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def get_html(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
                return r.read().decode('utf-8', errors='ignore')
        except Exception as e:
            if attempt == retries - 1:
                print(f"Failed {url}: {e}")
                return ""
            time.sleep(1)
    return ""

def scrape_schools():
    os.makedirs("data/raw/kemendikdasmen", exist_ok=True)
    
    # 1. Dikdas
    print("Fetching Dikdas main page...")
    html_dikdas = get_html("https://referensi.data.kemendikdasmen.go.id/pendidikan/dikdas")
    prov_links = re.findall(r'href=[\'"]([^\'"]+pendidikan/dikdas/(\d+)/1)[\'"]', html_dikdas)
    print(f"Found {len(prov_links)} province links for Dikdas.")
    
    dikdas_data = {} # key: (prov_code, kab_name) -> {sd, smp, total_dikdas}
    
    for full_url, prov_code in prov_links:
        # cache locally
        raw_file = f"data/raw/kemendikdasmen/dikdas_{prov_code}.html"
        if os.path.exists(raw_file):
            with open(raw_file, "r", encoding="utf-8") as f:
                html_p = f.read()
        else:
            html_p = get_html(full_url)
            with open(raw_file, "w", encoding="utf-8") as f:
                f.write(html_p)
            time.sleep(0.1)
            
        tables = re.findall(r'<table[^>]*>.*?</table>', html_p, re.DOTALL)
        if tables:
            rows = re.findall(r'<tr[^>]*>.*?</tr>', tables[0], re.DOTALL)
            for row in rows:
                cols = [c.strip() for c in re.findall(r'>([^<]+)<', row) if c.strip()]
                if len(cols) >= 5 and cols[0].isdigit():
                    kab_name = cols[1]
                    try:
                        sd = int(cols[2].replace('.', '').replace(',', ''))
                        smp = int(cols[3].replace('.', '').replace(',', ''))
                        tot = int(cols[4].replace('.', '').replace(',', ''))
                        dikdas_data[(prov_code, kab_name)] = {
                            "prov_code": prov_code,
                            "region_name": kab_name,
                            "edu_schools_sd": sd,
                            "edu_schools_smp": smp,
                            "edu_schools_dikdas_total": tot
                        }
                    except ValueError:
                        continue
                        
    print(f"Extracted {len(dikdas_data)} kab/kota for Dikdas.")
    
    # 2. Dikmen (SMA, SMK)
    print("Fetching Dikmen main page...")
    html_dikmen = get_html("https://referensi.data.kemendikdasmen.go.id/pendidikan/dikmen")
    dikmen_links = re.findall(r'href=[\'"]([^\'"]+pendidikan/dikmen/(\d+)/1)[\'"]', html_dikmen)
    print(f"Found {len(dikmen_links)} province links for Dikmen.")
    
    dikmen_data = {}
    for full_url, prov_code in dikmen_links:
        raw_file = f"data/raw/kemendikdasmen/dikmen_{prov_code}.html"
        if os.path.exists(raw_file):
            with open(raw_file, "r", encoding="utf-8") as f:
                html_p = f.read()
        else:
            html_p = get_html(full_url)
            with open(raw_file, "w", encoding="utf-8") as f:
                f.write(html_p)
            time.sleep(0.1)
            
        tables = re.findall(r'<table[^>]*>.*?</table>', html_p, re.DOTALL)
        if tables:
            rows = re.findall(r'<tr[^>]*>.*?</tr>', tables[0], re.DOTALL)
            for row in rows:
                cols = [c.strip() for c in re.findall(r'>([^<]+)<', row) if c.strip()]
                # Table format: No | Nama Kota/Kabupaten | SMA | SMK | SLB | Total
                if len(cols) >= 6 and cols[0].isdigit():
                    kab_name = cols[1]
                    try:
                        sma = int(cols[2].replace('.', '').replace(',', ''))
                        smk = int(cols[3].replace('.', '').replace(',', ''))
                        slb = int(cols[4].replace('.', '').replace(',', ''))
                        tot = int(cols[5].replace('.', '').replace(',', ''))
                        dikmen_data[(prov_code, kab_name)] = {
                            "edu_schools_sma": sma,
                            "edu_schools_smk": smk,
                            "edu_schools_slb": slb,
                            "edu_schools_dikmen_total": tot
                        }
                    except ValueError:
                        continue
                        
    print(f"Extracted {len(dikmen_data)} kab/kota for Dikmen.")
    
    # Merge Dikdas + Dikmen
    combined_rows = []
    for key, d in dikdas_data.items():
        prov_code, kab_name = key
        dm = dikmen_data.get(key, {})
        sma = dm.get("edu_schools_sma", 0)
        smk = dm.get("edu_schools_smk", 0)
        slb = dm.get("edu_schools_slb", 0)
        dikmen_tot = dm.get("edu_schools_dikmen_total", sma + smk + slb)
        grand_total = d["edu_schools_dikdas_total"] + dikmen_tot
        
        combined_rows.append({
            "kemendikdasmen_prov_code": prov_code,
            "region_name": kab_name,
            "edu_schools_sd": d["edu_schools_sd"],
            "edu_schools_smp": d["edu_schools_smp"],
            "edu_schools_sma": sma,
            "edu_schools_smk": smk,
            "edu_schools_slb": slb,
            "edu_schools_total": grand_total,
            "source": "Kemendikdasmen Referensi 2026"
        })
        
    out_csv = "data/kemendikdasmen_schools_kabkota.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        fields = [
            "kemendikdasmen_prov_code", "region_name", 
            "edu_schools_sd", "edu_schools_smp", "edu_schools_sma", 
            "edu_schools_smk", "edu_schools_slb", "edu_schools_total", "source"
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(combined_rows)
        
    print(f"Saved {len(combined_rows)} kab/kota to {out_csv}!")

if __name__ == "__main__":
    scrape_schools()
