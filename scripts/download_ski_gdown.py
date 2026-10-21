import gdown
import os

os.makedirs("data/raw/kemenkes", exist_ok=True)
url = "https://drive.google.com/uc?id=1rjNDG_f8xG6-Y9wmhJUnXhJ-vUFevVJC"
out = "data/raw/kemenkes/ski_2023_dalam_angka.pdf"

print("Downloading SKI 2023 Dalam Angka via gdown...")
gdown.download(url, out, quiet=False)

if os.path.exists(out):
    print("Download completed! File size:", os.path.getsize(out), "bytes")
else:
    print("Failed to download file.")
