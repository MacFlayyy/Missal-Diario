#!/usr/bin/env python3
"""Análise estática de todo o código do site. Falha em qualquer erro real.

- JavaScript da página (todos os <script> do index.html) e sw.js: ESLint
- CSS de todos os <style>: Stylelint (propriedades/valores/unidades inválidos)
- Scripts Python: pyflakes (nomes indefinidos, imports quebrados)
- Scripts de auditoria .cjs: ESLint
Uso: python scripts/lint/lint_code.py   (precisa de `npm ci` em scripts/lint)
"""
import re, subprocess, sys, tempfile, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
html = (ROOT / "index.html").read_text(encoding="utf-8")
work = Path(tempfile.mkdtemp())
scripts = [m.group(2) for m in re.finditer(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", html, re.S)
           if "json" not in m.group(1)]
(work / "page.js").write_text("\n;\n".join(scripts), encoding="utf-8")
shutil.copy(ROOT / "sw.js", work / "sw.js")
for f in (ROOT / "scripts").glob("*.cjs"):
    shutil.copy(f, work / f.name)
styles = [m.group(1) for m in re.finditer(r"<style[^>]*>(.*?)</style>", html, re.S)]
for i, css in enumerate(styles):
    (work / f"style{i}.css").write_text(css, encoding="utf-8")

bin_ = HERE / "node_modules" / ".bin"
results = []
results.append(subprocess.run([str(bin_ / "eslint"), "-c", str(HERE / "eslint.config.mjs"), "--no-warn-ignored",
                               "page.js", "sw.js", *[p.name for p in work.glob("*.cjs")]], cwd=work))
results.append(subprocess.run([str(bin_ / "stylelint"), *[p.name for p in work.glob("style*.css")],
                               "--config", str(HERE / "stylelint.json")], cwd=work))
py = subprocess.run([sys.executable, "-m", "pyflakes", *map(str, (ROOT / "scripts").glob("*.py"))],
                    capture_output=True, text=True)
serious = [l for l in py.stdout.splitlines() if re.search(r"undefined name|unable to detect undefined|syntax|invalid|referenced before assignment", l)]
for l in serious:
    print("pyflakes:", l)
ok = all(r.returncode == 0 for r in results) and not serious
print("CÓDIGO OK: JavaScript, CSS e Python sem erros." if ok else "CÓDIGO COM ERROS (veja acima).")
sys.exit(0 if ok else 1)
