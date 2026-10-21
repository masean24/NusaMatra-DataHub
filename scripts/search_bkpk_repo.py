import urllib.request
import re
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://repository.badankebijakan.kemkes.go.id/cgi/search/archive/simple?q=SSGI"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        html = r.read().decode('utf-8', errors='ignore')
        print("Search status 200, length:", len(html))
        # find eprint links
        links = re.findall(r'href=[\'"](https?://repository\.badankebijakan\.kemkes\.go\.id/id/eprint/\d+/[^\'"]*)[\'"]', html)
        if not links:
            links = re.findall(r'href=[\'"](/id/eprint/\d+/[^\'"]*)[\'"]', html)
        print("Found eprint links:", len(links))
        for l in links[:10]:
            print(" ", l)
except Exception as e:
    print("Error:", e)
