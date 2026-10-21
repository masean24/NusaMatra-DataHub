import urllib.request
import re
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Check Flipbook files
for test_url in [
    "https://inarisk.bnpb.go.id/IRBI-2024/files/basic-html/page1.html",
    "https://inarisk.bnpb.go.id/IRBI-2024/files/search/book_config.json",
    "https://inarisk.bnpb.go.id/IRBI-2024/javascript/main.js",
    "https://inarisk.bnpb.go.id/IRBI-2024/files/mobile/index.html"
]:
    try:
        req = urllib.request.Request(test_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
            print(f"URL: {test_url} -> Status: {r.status}, length: {len(r.read())}")
    except Exception as e:
        print(f"URL: {test_url} -> Error: {e}")

# Check hasil-ski-2023
try:
    req = urllib.request.Request("https://www.badankebijakan.kemkes.go.id/hasil-ski-2023/", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
        html = r.read().decode('utf-8', errors='ignore')
        print("\nhasil-ski-2023 links:")
        for link in set(re.findall(r'href=[\'"]([^\'"]+)[\'"]', html)):
            if any(k in link.lower() for k in ["drive.google.com", ".pdf", "download", "stunting"]):
                print(link)
except Exception as e:
    print("Error hasil-ski:", e)
