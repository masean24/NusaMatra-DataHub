import urllib.request
import re
import ssl
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Test fetching Dikdas list
url = "https://referensi.data.kemendikdasmen.go.id/pendidikan/dikdas"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
    html = r.read().decode('utf-8', errors='ignore')
    # Find links to provinces
    prov_links = re.findall(r'href=[\'"]([^\'"]+pendidikan/dikdas/\d+/1)[\'"]', html)
    print("Found province links:", len(prov_links))

# Test fetching first province (DKI)
sample_url = prov_links[0]
print("Fetching sample:", sample_url)
req_p = urllib.request.Request(sample_url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req_p, timeout=10, context=ctx) as r:
    html_p = r.read().decode('utf-8', errors='ignore')
    tables = re.findall(r'<table[^>]*>.*?</table>', html_p, re.DOTALL)
    if tables:
        rows = re.findall(r'<tr[^>]*>.*?</tr>', tables[0], re.DOTALL)
        for row in rows[1:6]:
            cols = [c.strip() for c in re.findall(r'>([^<]+)<', row) if c.strip()]
            if len(cols) >= 4 and cols[0].isdigit():
                print(" ", cols[1], "-> SD:", cols[2], "SMP:", cols[3], "Total:", cols[4])
