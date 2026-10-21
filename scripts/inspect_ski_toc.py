import pypdf
import sys

sys.stdout.reconfigure(encoding='utf-8')
PDF_PATH = "data/raw/kemenkes/ski_2023_dalam_angka.pdf"

reader = pypdf.PdfReader(PDF_PATH)
print("Scanning pages 1 to 40 for Daftar Isi / Daftar Tabel...")

for p in range(min(40, len(reader.pages))):
    text = reader.pages[p].extract_text() or ""
    lower = text.lower()
    if any(k in lower for k in ["daftar isi", "daftar tabel", "stunting", "gizi balita", "status gizi", "tb/u"]):
        print(f"\n=== Page {p + 1} ===")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for l in lines:
            if any(k in l.lower() for k in ["tabel", "gizi", "stunting", "pendek", "balita", "bab", "lampiran"]):
                print(" ", l)
