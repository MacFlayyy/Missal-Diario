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
