import urllib.request
import re
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://referensi.data.kemendikdasmen.go.id/pendidikan/dikdas"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, context=ctx) as r:
    html = r.read().decode('utf-8', errors='ignore')
    # Find links to provinces
    links = re.findall(r'href=[\'"]([^\'"]+pendidikan/dikdas/[^\'"]+)[\'"]', html)
    print("Found province links:", len(links))
    for l in links[:5]:
        print(" ", l)
