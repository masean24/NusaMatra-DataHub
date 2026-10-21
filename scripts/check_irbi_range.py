import urllib.request
import ssl
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for p in range(50, 56):
    url = f"https://inarisk.bnpb.go.id/IRBI-2024/files/basic-html/page{p}.html"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            html = r.read().decode("utf-8", errors="ignore")
            # find all numbers at beginning of lines or table rows
            matches = re.findall(r'^\s*(\d{1,3})\s+([A-Z\s]+?)\s+([A-Z\s]+?)\s+(\d+\.\d{2})\s+([A-Z]+)', html, re.M)
            if not matches:
                # try finding any row
                text = " ".join(re.findall(r'>([^<]+)<', html))
                print(f"Page {p}: text snippet -> {text[:150]}")
            else:
                print(f"Page {p}: rows {matches[0][0]} to {matches[-1][0]} (total {len(matches)} rows)")
    except Exception as e:
        print(f"Page {p}: {e}")
