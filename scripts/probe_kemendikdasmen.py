import urllib.request
import re
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://data.kemendikdasmen.go.id/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
    html = r.read().decode('utf-8', errors='ignore')
    links = set(re.findall(r'href=[\'"]([^\'"]+)[\'"]', html))
    print(f"Total links: {len(links)}")
    for l in sorted(links):
        if not l.startswith("#") and not l.startswith("javascript"):
            print(" ", l)
