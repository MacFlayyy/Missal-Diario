#!/usr/bin/env python3
"""Cria ícones rasterizados a partir do SVG livre de direitos do próprio site."""
from pathlib import Path
try:
    import cairosvg
except ImportError as exc:
    raise SystemExit("Instale cairosvg para criar os PNG do PWA.") from exc

root = Path(__file__).resolve().parents[1]
src = root / "app-icon.svg"
for size in (180, 192, 512):
    target = root / f"app-icon-{size}.png"
    cairosvg.svg2png(
        url=str(src), write_to=str(target),
        output_width=size, output_height=size
    )
    if not target.is_file() or target.stat().st_size < 500:
        raise SystemExit(f"PNG inválido: {target.name}")
    print(f"Ícone PWA gerado: {target.name} ({target.stat().st_size} bytes)")

# Nomes que navegadores e apps procuram sozinhos na raiz do site (sem link na
# página): sem eles alguns mostram ícone antigo guardado ou nenhum ícone.
import shutil
from PIL import Image
shutil.copyfile(root / "app-icon-180.png", root / "apple-touch-icon.png")
Image.open(root / "app-icon-192.png").convert("RGBA").save(
    root / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
for name in ("apple-touch-icon.png", "favicon.ico"):
    if (root / name).stat().st_size < 300:
        raise SystemExit(f"Ícone inválido: {name}")
    print(f"Ícone gerado: {name}")
