import urllib.request
import re
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://stunting.go.id/?s=buku+saku+ssgi"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
        html = r.read().decode('utf-8', errors='ignore')
        links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', html)
        for l in links:
            if "buku" in l.lower() or "ssgi" in l.lower() or "pdf" in l.lower():
                print(l)
except Exception as e:
    print("Error:", e)
