import pypdf
import sys
import re
import csv

sys.stdout.reconfigure(encoding='utf-8')
PDF_PATH = "data/raw/kemenkes/ski_2023_dalam_angka.pdf"

print("Reading PDF metadata & pages...")
reader = pypdf.PdfReader(PDF_PATH)
num_pages = len(reader.pages)
print(f"Total pages: {num_pages}")

# Find pages with Stunting tables
# In SKI 2023, stunting is usually presented in "Tabel ... Prevalensi Status Gizi Balita ... menurut Kabupaten/Kota"
matches = []
for i in range(num_pages):
    # check text snippet
    try:
        t = reader.pages[i].extract_text() or ""
    except Exception:
        continue
    if "stunting" in t.lower() or "pendek dan sangat pendek" in t.lower():
        if "kabupaten" in t.lower() or "provinsi" in t.lower():
            # Check if it has a table header
            matches.append((i + 1, t[:200].replace('\n', ' ')))

print(f"Found {len(matches)} candidate pages for stunting:")
for p, snippet in matches[:25]:
    print(f"Page {p}: {snippet}")
