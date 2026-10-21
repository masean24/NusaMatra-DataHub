import urllib.request
import ssl
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for p in range(5, 12):
    url = f"https://inarisk.bnpb.go.id/IRBI-2024/files/basic-html/page{p}.html"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            html = r.read().decode("utf-8", errors="ignore")
            # Find body
            body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.I)
            if body_match:
                body = body_match.group(1)
                # strip script tags
                body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL | re.I)
                body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.I)
                # extract text
                lines = [line.strip() for line in re.findall(r'>([^<]+)<', body) if line.strip() and not line.strip().startswith('var ') and not line.strip().startswith('function')]
                print(f"=== Page {p} ===")
                print("\n".join(lines[:30]))
    except Exception as e:
        print(f"Page {p}: {e}")
