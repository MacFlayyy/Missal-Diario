#!/usr/bin/env python3
"""Gera versão leve da logomarca preservando o PNG como fallback."""
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parents[1]
src=root/"brand-logo.png"
dst=root/"brand-logo.webp"
if not src.is_file():
    raise SystemExit("Logo original ausente.")
with Image.open(src) as image:
    image.save(dst,format="WEBP",quality=88,method=6)
if dst.stat().st_size<3000 or dst.stat().st_size>=src.stat().st_size:
    raise SystemExit("Falha na otimização da logomarca.")
print(f"Logo otimizada: {src.stat().st_size} B → {dst.stat().st_size} B")
