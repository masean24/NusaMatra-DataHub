import urllib.request
import re
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request("https://inarisk.bnpb.go.id/IRBI-2024/", headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
    html = resp.read().decode("utf-8", errors="ignore")
    print("--- inarisk 2024 html snippet ---")
    print(html[:2000])

req2 = urllib.request.Request("https://www.badankebijakan.kemkes.go.id/ski-2023-dalam-angka/", headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req2, timeout=10, context=ctx) as resp:
    html2 = resp.read().decode("utf-8", errors="ignore")
    print("\n--- badankebijakan links snippet ---")
    for link in re.findall(r'href=[\'"]([^\'"]+)[\'"]', html2):
        if any(w in link.lower() for w in ["drive", "download", "ski", "pdf", "file"]):
            print(link)
