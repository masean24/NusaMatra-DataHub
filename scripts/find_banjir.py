import urllib.request
import ssl
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for p in range(212, 226):
    url = f"https://inarisk.bnpb.go.id/IRBI-2024/files/basic-html/page{p}.html"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            html = r.read().decode('utf-8', errors='ignore')
            text = re.sub(r'<[^>]+>', ' ', html)
            text = " ".join(text.split())
            if "BANJIR" in text.upper():
                print(f"Page {p} contains BANJIR: {text[:150]}")
    except Exception as e:
        print(f"Page {p}: {e}")
