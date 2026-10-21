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

# Test page 38 text
url = "https://inarisk.bnpb.go.id/IRBI-2024/files/basic-html/page38.html"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, context=ctx) as r:
    html = r.read().decode('utf-8', errors='ignore')

# Look at lines inside the table
text = re.sub(r'<[^>]+>', '\n', html)
lines = [l.strip() for l in text.split('\n') if l.strip()]

rows = []
for line in lines:
    # Match pattern: NO KABUPATEN/KOTA PROVINSI SKOR KELAS
    # e.g.: 1 MANDAILING NATAL SUMATERA UTARA 214.80 TINGGI
    # or: 10 KOTA BAU BAU SULAWESI TENGGARA 194.80 TINGGI
    m = re.match(r'^(\d{1,3})\s+(.+?)\s+([A-Z\s]+?)\s+(\d+\.\d{2})\s+([A-Z]+)$', line)
    if m:
        no, kab, prov, score, kelas = m.groups()
        rows.append({
            "rank": int(no),
            "region_name": kab.strip(),
            "province_name": prov.strip(),
            "irbi_score": float(score),
            "risk_class": kelas.strip()
        })

print(f"Parsed {len(rows)} rows from page 38:")
for r in rows[:5]:
    print(r)
print("Last row:", rows[-1] if rows else "none")
