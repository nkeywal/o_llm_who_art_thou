#!/usr/bin/env bash
set -euo pipefail

# Liste des modèles à cloner
MODELS=(
  "qwen3.5:9b"
  "qwen3:8b"
  "nemotron-3-nano:latest"
  "gpt-oss:20b"
  "deepseek-r1:7b"
  "deepseek-r1:14b"
  "magistral:24b"
)

SUFFIX="-noprompt"

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

for model in "${MODELS[@]}"; do
  clone="${model}${SUFFIX}"
  safe_name="$(echo "$model" | sed 's#[/:]#_#g')"
  modelfile="$workdir/${safe_name}.Modelfile"

  echo "=== Processing: $model -> $clone ==="

  ollama show --modelfile "$model" \
  | python3 -c '
import sys, re

s = sys.stdin.read()

# Supprime le bloc LICENSE """ ... """
s = re.sub(r"(?ms)^LICENSE\s+\"\"\".*?^\"\"\"\s*\n?", "", s)

# Supprime les lignes SYSTEM ...
s = re.sub(r"(?m)^SYSTEM\b.*\n?", "", s)

# Supprime les lignes MESSAGE ...
s = re.sub(r"(?m)^MESSAGE\b.*\n?", "", s)

# Remplace tout bloc TEMPLATE ... par TEMPLATE {{ .Prompt }}
s = re.sub(
    r"(?ms)^TEMPLATE\b.*?(?=^(?:FROM|PARAMETER|SYSTEM|ADAPTER|LICENSE|MESSAGE|REQUIRES|TEMPLATE|PARSER|RENDERER)\b|\Z)",
    "TEMPLATE {{ .Prompt }}\n",
    s,
)

# Si jamais il n y a pas de TEMPLATE, on l ajoute après FROM
if not re.search(r"(?m)^TEMPLATE\b", s):
    s = re.sub(r"(?m)^(FROM\b.*\n)", r"\1TEMPLATE {{ .Prompt }}\n", s, count=1)

print(s, end="")
' > "$modelfile"

  echo "--- Cleaned Modelfile for $clone ---"
  cat "$modelfile"
  echo "------------------------------------"

  ollama create "$clone" -f "$modelfile"
  echo "Created: $clone"
  echo
done

echo "Done."
