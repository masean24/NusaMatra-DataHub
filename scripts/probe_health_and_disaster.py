import urllib.request
import re
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

urls = [
    "https://www.badankebijakan.kemkes.go.id/ski-2023-dalam-angka/",
    "https://inarisk.bnpb.go.id/IRBI-2024/",
    "https://inarisk.bnpb.go.id/IRBI-2023/"
]

for url in urls:
    print(f"\n--- Checking {url} ---")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            print(f"Status 200, length: {len(html)}")
            pdf_links = re.findall(r'href=[\'"]([^\'"]+?\.pdf[^\'"]*)[\'"]', html, re.I)
            print("PDF links found:", pdf_links[:5])
            xlsx_links = re.findall(r'href=[\'"]([^\'"]+?\.(?:xlsx|xls|csv)[^\'"]*)[\'"]', html, re.I)
            print("Table links found:", xlsx_links[:5])
    except Exception as e:
        print("Error:", e)
