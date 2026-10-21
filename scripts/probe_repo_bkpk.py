import urllib.request
import re
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://repository.badankebijakan.kemkes.go.id/"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
        print("Status:", r.status)
        html = r.read().decode('utf-8', errors='ignore')
        print("Length:", len(html))
except Exception as e:
    print("Error:", e)
