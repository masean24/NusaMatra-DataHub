import urllib.request
import ssl
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Test pages
for p in [1, 2, 3, 4, 5, 10, 20, 50, 100, 200, 250, 300]:
    url = f"https://inarisk.bnpb.go.id/IRBI-2024/files/basic-html/page{p}.html"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            html = r.read().decode("utf-8", errors="ignore")
            # extract text inside div or span
            text = " ".join(re.findall(r'>([^<]+)<', html))
            text = " ".join(text.split())
            print(f"Page {p} (status 200, len {len(html)}): {text[:120]}")
    except Exception as e:
        print(f"Page {p}: {e}")
