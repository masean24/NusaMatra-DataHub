import urllib.request
import re
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://referensi.data.kemendikdasmen.go.id/pendidikan/dikdas"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
        html = r.read().decode('utf-8', errors='ignore')
        print("Status 200, length:", len(html))
        # check table
        tables = re.findall(r'<table[^>]*>.*?</table>', html, re.DOTALL)
        print("Found tables:", len(tables))
        if tables:
            rows = re.findall(r'<tr[^>]*>.*?</tr>', tables[0], re.DOTALL)
            print("Rows in table 0:", len(rows))
            for row in rows[:5]:
                clean = " | ".join([c.strip() for c in re.findall(r'>([^<]+)<', row) if c.strip()])
                print(" ", clean)
except Exception as e:
    print("Error:", e)
