#!/usr/bin/env bash
# deploy.sh — merge la rama actual en main y pushea a los dos remotes.
#
# Vercel y Render deployan desde RobonicBaluta/tumor-tracker (remote `personal`),
# no desde jonzuru/zuruweb (remote `origin`). Este script asegura que ambos
# remotes reciben main para que los webhooks disparen correctamente.
#
# Uso:
#   ./deploy.sh                   # mergea la rama actual en main
#   ./deploy.sh -m "msg"          # con mensaje de commit personalizado para el merge
#   ./deploy.sh --no-merge        # no mergea: asume que ya estás en main, solo pushea
#
# Salida: deja al user en la rama donde estaba.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
MERGE_MSG=""
SKIP_MERGE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -m|--message) MERGE_MSG="$2"; shift 2 ;;
    --no-merge)   SKIP_MERGE=1; shift ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "argumento desconocido: $1"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------
ORIG_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "→ rama actual: $ORIG_BRANCH"

if [[ -n "$(git status --porcelain | grep -v '^?? \.claude/' | grep -v '\.claude/settings.local.json')" ]]; then
  echo "✗ hay cambios sin commitear (excluyendo .claude/). aborto."
  git status --short
  exit 1
fi

# Verifica los dos remotes
git remote get-url origin   >/dev/null 2>&1 || { echo "✗ falta remote 'origin'"; exit 1; }
git remote get-url personal >/dev/null 2>&1 || { echo "✗ falta remote 'personal' (RobonicBaluta/tumor-tracker)"; exit 1; }

# ---------------------------------------------------------------------------
# Restaurar rama original aunque algo falle
# ---------------------------------------------------------------------------
restore_branch() {
  local code=$?
  if [[ "$ORIG_BRANCH" != "$(git rev-parse --abbrev-ref HEAD)" ]]; then
    echo "↩ volviendo a $ORIG_BRANCH"
    git checkout "$ORIG_BRANCH" >/dev/null 2>&1 || true
  fi
  exit $code
}
trap restore_branch EXIT

# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------
if [[ $SKIP_MERGE -eq 0 ]]; then
  if [[ "$ORIG_BRANCH" == "main" ]]; then
    echo "✗ ya estás en main. usa --no-merge si solo quieres pushear."
    exit 1
  fi

  echo "→ checkout main + pull origin/main"
  git checkout main
  git pull origin main --ff-only

  if [[ -z "$MERGE_MSG" ]]; then
    MERGE_MSG="Merge $ORIG_BRANCH"
  fi
  echo "→ merge --no-ff $ORIG_BRANCH"
  git merge --no-ff "$ORIG_BRANCH" -m "$MERGE_MSG"
fi

# ---------------------------------------------------------------------------
# Push a los dos remotes
# ---------------------------------------------------------------------------
echo ""
echo "→ push origin/main (jonzuru/zuruweb)"
git push origin main

echo ""
echo "→ push personal/main (RobonicBaluta/tumor-tracker) ← este dispara Vercel + Render"
git push personal main

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "✓ pushed. los servicios deberían deployar:"
echo "  Vercel:  https://tumor-tracker-ecru.vercel.app/    (~30-60s)"
echo "  Render:  https://tumor-tracker-api.onrender.com/   (~2-4 min, free tier)"
echo ""
echo "verifica con:"
echo "  curl -s https://tumor-tracker-api.onrender.com/healthz/redis"
