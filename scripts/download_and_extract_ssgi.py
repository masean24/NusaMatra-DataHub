import urllib.request
import ssl
import sys
import os
import pypdf
import re
import csv

sys.stdout.reconfigure(encoding='utf-8')
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

PDF_URL = "https://ayosehat.kemkes.go.id/pub/files/files/BUKU%20SAKU%20Hasil%20Survei%20Status%20Gizi%20Indonesia%20(SSGI)%202022.pdf"
LOCAL_PDF = "data/raw/kemenkes/ssgi_2022.pdf"

def download_pdf():
    os.makedirs("data/raw/kemenkes", exist_ok=True)
    if os.path.exists(LOCAL_PDF) and os.path.getsize(LOCAL_PDF) > 100000:
        print(f"PDF already downloaded: {LOCAL_PDF} ({os.path.getsize(LOCAL_PDF)} bytes)")
        return
    print(f"Downloading SSGI 2022 PDF from {PDF_URL}...")
    req = urllib.request.Request(PDF_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp, open(LOCAL_PDF, "wb") as f:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            f.write(chunk)
    print(f"Downloaded successfully: {os.path.getsize(LOCAL_PDF)} bytes")

def inspect_pdf():
    reader = pypdf.PdfReader(LOCAL_PDF)
    num_pages = len(reader.pages)
    print(f"Total pages in SSGI 2022 PDF: {num_pages}")
    
    # Search for pages with kabupaten tables
    stunting_pages = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if "stunting" in text.lower() and ("kabupaten" in text.lower() or "kota" in text.lower()):
            stunting_pages.append(idx + 1)
    print(f"Pages mentioning stunting & kabupaten/kota: {len(stunting_pages)} pages")
    print(f"Sample pages: {stunting_pages[:15]}")
    
    # Print sample text from first matching page
    if stunting_pages:
        p_idx = stunting_pages[0] - 1
        print(f"\n--- Content of Page {stunting_pages[0]} ---")
        print(reader.pages[p_idx].extract_text()[:1000])

if __name__ == "__main__":
    download_pdf()
    inspect_pdf()
