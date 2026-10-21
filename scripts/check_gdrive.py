import urllib.request
import re
import ssl
import sys

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

drive_ids = [
    "1rjNDG_f8xG6-Y9wmhJUnXhJ-vUFevVJC",
    "1NMZwTtFMamkmMe-H8OpZwan105kiSQtq"
]

for fid in drive_ids:
    url = f"https://drive.google.com/file/d/{fid}/view"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            html = r.read().decode('utf-8', errors='ignore')
            title_match = re.search(r'<title>([^<]+)</title>', html)
            title = title_match.group(1) if title_match else "unknown"
            print(f"File ID {fid} -> Title: {title}")
    except Exception as e:
        print(f"File ID {fid} -> Error: {e}")
