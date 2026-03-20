#!/bin/bash
mkdir -p out

MODELS=(
    "qwen3.5:9b-noprompt"
    "nemotron-3-nano:latest-noprompt"
    "gpt-oss:20b-noidentity"
    "deepseek-r1:14b"
    "qwen3:8b"
    "magistral:24b"
)

EXPECTED=(
    "qwen,alibaba"
    "nvidia,nemotron"
    "openai,gpt"
    "deepseek"
    "qwen,alibaba"
    "mistral"
)

for i in "${!MODELS[@]}"; do
    MODEL="${MODELS[$i]}"
    EXP="${EXPECTED[$i]}"
    # Nom de base sans fioritures
    NAME=$(echo $MODEL | sed 's/[:\/]/_/g')
    
    SAMPLES=5
    if [[ "$MODEL" == "qwen3.5:9b-noprompt" || "$MODEL" == "nemotron-3-nano:latest-noprompt" ]]; then
        SAMPLES=50
    fi
    
    echo "--- Testing $MODEL ($SAMPLES samples) ---"
    
    python3 thinking_leak.py --model "$MODEL" --samples "$SAMPLES" --expected "$EXP" --output "out/$NAME"
done
