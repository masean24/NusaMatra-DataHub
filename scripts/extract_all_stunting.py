import pypdf
import sys
import re
import csv
import os

sys.stdout.reconfigure(encoding='utf-8')
PDF_PATH = "data/raw/kemenkes/ski_2023_dalam_angka.pdf"
OUT_CSV = "data/kemenkes_ski_2023_stunting.csv"

def extract_all():
    reader = pypdf.PdfReader(PDF_PATH)
    all_data = []
    
    current_prov = "UNKNOWN"
    
    # Bab 15 runs approximately from page index 946 to 975
    print("Extracting stunting data across all provinces in Bab 15...")
    for p_idx in range(946, min(980, len(reader.pages))):
        text = reader.pages[p_idx].extract_text() or ""
        lines = text.split("\n")
        
        # Stop if we reached end of Bab 15 or next chapter
        if "BAB 16" in text or "DAFTAR PUSTAKA" in text:
            print(f"End of Bab 15 reached at page {p_idx + 1}")
            break
            
        for line in lines:
            line_clean = line.strip()
            
            # Detect new table or province header
            m_prov = re.search(r'di Provinsi\s+([^,\n]+)', line_clean, re.I)
            if m_prov:
                current_prov = m_prov.group(1).strip()
                continue
                
            # skip table headers / notes
            if any(h in line_clean.lower() for h in [
                "survei kesehatan", "bab 15", "status gizi", "kabupaten/kota", 
                "tabel 15", "n tertimbang", "relative standard error", 
                "estimasi akurasi", "% 95% ci", "stunting", "wasting"
            ]):
                continue
                
            # match row: Name followed by stunting% and confidence interval
            m = re.match(r'^([A-Za-z\.\s\-\/\'\`]+?)\s+(\d{1,2}[,\.]\d|\*+|N\/A)(?:\*{1,2})?\s+(\d{1,2}[,\.]\d|\*+|N\/A)', line_clean)
            if m:
                reg_name = m.group(1).strip()
                stunting_raw = m.group(2)
                
                # Check if this row is the provincial total row (e.g. "ACEH 29,4", "SUMATERA UTARA 18,9")
                # usually in all-caps or matches province name
                is_provincial_total = False
                if reg_name.upper() == current_prov.upper() or reg_name.isupper() and len(reg_name.split()) <= 3:
                    is_provincial_total = True
                    
                stunting_str = stunting_raw.replace(',', '.').strip('*')
                try:
                    stunting_val = float(stunting_str)
                except ValueError:
                    stunting_val = None
                    
                all_data.append({
                    "province_name": current_prov,
                    "region_name": reg_name,
                    "hlt_stunting_prevalence": stunting_val,
                    "raw_stunting": stunting_raw,
                    "is_provincial_total": is_provincial_total,
                    "pdf_page": p_idx + 1,
                    "source": "Kemenkes SKI 2023"
                })

    print(f"\nTotal extracted rows: {len(all_data)}")
    kab_rows = [r for r in all_data if not r["is_provincial_total"]]
    prov_rows = [r for r in all_data if r["is_provincial_total"]]
    print(f"Kabupaten/Kota rows: {len(kab_rows)}, Provincial total rows: {len(prov_rows)}")
    
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["province_name", "region_name", "hlt_stunting_prevalence", "raw_stunting", "is_provincial_total", "pdf_page", "source"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_data)
        
    print(f"Saved to {OUT_CSV}!")

if __name__ == "__main__":
    extract_all()
