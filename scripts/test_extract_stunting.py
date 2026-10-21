import pypdf
import sys
import re
import csv

sys.stdout.reconfigure(encoding='utf-8')
PDF_PATH = "data/raw/kemenkes/ski_2023_dalam_angka.pdf"

reader = pypdf.PdfReader(PDF_PATH)

def extract_rows_from_page(p_idx):
    text = reader.pages[p_idx].extract_text() or ""
    lines = text.split("\n")
    
    # find province name
    prov_match = re.search(r'di Provinsi\s+([^,\n]+)', text, re.I)
    current_prov = prov_match.group(1).strip() if prov_match else "UNKNOWN"
    
    # Extract data lines
    # Format: RegionName Stunting% CI_min - CI_max ...
    # e.g.: Simeulue 30,7 26,6 - 35,1 ...
    # or: Kota Banda Aceh 21,7 ...
    # or: N/A or *
    page_rows = []
    for line in lines:
        line_clean = line.strip()
        # skip header lines
        if any(h in line_clean.lower() for h in ["survei kesehatan", "bab 15", "status gizi", "kabupaten/kota", "tabel 15", "n tertimbang", "relative standard error", "estimasi akurasi", "% 95% ci"]):
            continue
        # match: name followed by a float (comma as decimal, optionally with **) or * or N/A
        m = re.match(r'^([A-Za-z\.\s\-\/]+?)\s+(\d{1,2}[,\.]\d|\*+|N\/A)(?:\*{1,2})?\s+(\d{1,2}[,\.]\d|\*+|N\/A)', line_clean)
        if m:
            reg_name = m.group(1).strip()
            stunting_str = m.group(2).replace(',', '.').strip('*')
            try:
                stunting_val = float(stunting_str)
            except ValueError:
                stunting_val = None
            
            page_rows.append({
                "province": current_prov,
                "region_name": reg_name,
                "hlt_stunting_prevalence": stunting_val,
                "raw_stunting": m.group(2),
                "raw_line": line_clean
            })
    return current_prov, page_rows

# Test pages 947 (Aceh) and 948 (Sumut)
for p in [946, 947, 948, 949, 950]:
    prov, rows = extract_rows_from_page(p)
    print(f"\nPage {p + 1} - Prov: {prov} ({len(rows)} rows)")
    for r in rows[:4]:
        print(" ", r["region_name"], "-> Stunting:", r["hlt_stunting_prevalence"], "%")
    if rows:
        print("  Last:", rows[-1]["region_name"], "-> Stunting:", rows[-1]["hlt_stunting_prevalence"], "%")
