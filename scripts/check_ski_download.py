import urllib.request
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

fid = "1rjNDG_f8xG6-Y9wmhJUnXhJ-vUFevVJC"
url = f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        print("Status:", r.status)
        print("Content-Type:", r.headers.get("Content-Type"))
        print("Content-Length:", r.headers.get("Content-Length"))
except Exception as e:
    print("Error:", e)
