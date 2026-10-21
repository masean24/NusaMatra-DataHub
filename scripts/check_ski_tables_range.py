import pypdf
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')
PDF_PATH = "data/raw/kemenkes/ski_2023_dalam_angka.pdf"

reader = pypdf.PdfReader(PDF_PATH)
tables = []
for idx in range(946, min(1005, len(reader.pages))):
    text = reader.pages[idx].extract_text() or ""
    # normalize spaces and newlines
    flat = " ".join(text.split())
    m = re.search(r'Tabel 15\.\s*(\d+)\s+Prevalensi Status Gizi Balita.*?di Provinsi\s+([^,]+)', flat, re.I)
    if m:
        tables.append((idx, int(m.group(1)), m.group(2).strip()))

print(f"Found {len(tables)} province tables:")
for idx, num, prov in tables:
    print(f"Table 15.{num:02d} (page {idx + 1}): {prov}")
