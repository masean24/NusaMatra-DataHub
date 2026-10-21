import urllib.request
import ssl
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for p in [210, 226, 278]:
    url = f"https://inarisk.bnpb.go.id/IRBI-2024/files/basic-html/page{p}.html"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            html = r.read().decode("utf-8", errors="ignore")
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.I)
            lines = [l.strip() for l in re.findall(r'>([^<]+)<', html) if l.strip() and not l.strip().startswith('&nbsp;')]
            print(f"=== Page {p} ===")
            print("\n".join(lines[:30]))
    except Exception as e:
        print(f"Page {p}: {e}")
