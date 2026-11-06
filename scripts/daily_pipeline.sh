#!/usr/bin/env bash
# Pipeline diário do Missal Diário, com rede de segurança.
#
# 1ª tentativa: gera o dia, aplica os folhetos e roda TODAS as verificações.
# Se algo falhar por causa de um folheto (leitura ruim do PDF escaneado, regra
# nova etc.), o site NÃO fica sem o dia: as mudanças do folheto são desfeitas,
# o dia é gerado de novo pelo Missal e TODAS as verificações rodam outra vez.
# Nada é publicado sem passar nos testes; só o folheto problemático fica de fora
# e é avisado (aviso no GitHub + issue no repositório).
set -u

FILES="data.js status.js index.html sw.js Missal-Diario-Standalone.html"
SNAP="$(mktemp -d)"

run_checks() {
  python scripts/validate_daily.py \
  && python scripts/bump_daily_version.py \
  && python scripts/build_standalone.py \
  && python scripts/verify_daily.py \
  && python scripts/test_regressions.py \
  && python scripts/check_missal_references.py
}

python scripts/generate_daily.py || exit 1

for f in $FILES; do cp "$f" "$SNAP/$f"; done

LOG="$(mktemp)"
if { python scripts/update_folheto.py && run_checks; } 2>&1 | tee "$LOG"; [ "${PIPESTATUS[0]}" -eq 0 ]; then
  echo "Pipeline completo com folhetos: OK"
  exit 0
fi

echo "::warning title=Folheto não aplicado::A leitura de algum folheto falhou nas verificações. Publicando o dia pelo Missal, sem as mudanças do folheto."
for f in $FILES; do cp "$SNAP/$f" "$f"; done

if ! run_checks; then
  echo "::error::As verificações falharam também sem os folhetos. Nada foi publicado."
  exit 1
fi

if [ -n "${GITHUB_OUTPUT:-}" ]; then echo "fallback=1" >> "$GITHUB_OUTPUT"; fi
{
  echo "## ⚠️ Folheto não aplicado nesta execução"
  echo "O dia foi publicado normalmente pelo Missal. Trecho do erro:"
  echo '```'
  grep -E "AssertionError|Error|FALHA|falh" "$LOG" | tail -15
  echo '```'
} > /tmp/folheto-falha.md
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then cat /tmp/folheto-falha.md >> "$GITHUB_STEP_SUMMARY"; fi
exit 0
