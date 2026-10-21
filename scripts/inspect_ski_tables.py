import pypdf
import sys

sys.stdout.reconfigure(encoding='utf-8')
PDF_PATH = "data/raw/kemenkes/ski_2023_dalam_angka.pdf"

reader = pypdf.PdfReader(PDF_PATH)
print("Inspecting pages 908 and 909...")

# Note: PDF page index might be offset from printed page number 908
# Let's search around page 900-950 for "Tabel 15.1"
target_idx = None
for idx in range(850, min(1000, len(reader.pages))):
    text = reader.pages[idx].extract_text() or ""
    if "Tabel 15.1" in text or "Tabel 15. 1" in text:
        target_idx = idx
        break

if target_idx is not None:
    print(f"Found Tabel 15.1 at PDF page index {target_idx + 1}!")
    print("\n--- Content of Tabel 15.1 ---")
    print(reader.pages[target_idx].extract_text())
else:
    print("Could not find Tabel 15.1 in range 850-1000. Let's scan all pages.")
