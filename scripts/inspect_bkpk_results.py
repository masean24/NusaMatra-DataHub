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
with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
    html = r.read().decode('utf-8', errors='ignore')
    for m in re.finditer(r'<tr[^>]*>.*?</tr>', html, re.DOTALL):
        row = m.group(0)
        clean = " ".join(re.findall(r'>([^<]+)<', row))
        clean = " ".join(clean.split())
        if "SSGI" in clean.upper() or "STUNTING" in clean.upper():
            print("\nMatch:", clean[:200])
            links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', row)
            print("Links:", links)
