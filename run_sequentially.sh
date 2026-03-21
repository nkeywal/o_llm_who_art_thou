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
    "qwen,alibaba,tongyi"
    "nvidia,nemotron"
    "openai,gpt"
    "deepseek"
    "qwen,alibaba,tongyi"
    "mistral"
)

# On utilise Gemma 3 27B comme juge pour plus de fiabilité et de vitesse sur l'évaluation
JUDGE="gemma3:27b-it-qat"

for i in "${!MODELS[@]}"; do
    MODEL="${MODELS[$i]}"
    EXP="${EXPECTED[$i]}"
    NAME=$(echo $MODEL | sed 's/[:\/]/_/g')
    
    SAMPLES=5
    if [[ "$MODEL" == "qwen3.5:9b-noprompt" || "$MODEL" == "nemotron-3-nano:latest-noprompt" ]]; then
        SAMPLES=50
    fi
    
    echo "--- Testing $MODEL ($SAMPLES samples) ---"
    
    # Correction: Il faut passer explicitement --input pour sauter la Phase 1
    INPUT_ARG=""
    if [[ -f "out/${NAME}_phase1.json" ]]; then
        echo "Found existing Phase 1 file, loading from it."
        INPUT_ARG="--input out/${NAME}_phase1.json"
    elif [[ -f "out/${NAME}_phase2.json" ]]; then
         echo "Found existing Phase 2 file, loading from it."
        INPUT_ARG="--input out/${NAME}_phase2.json"
    fi
    
    python3 thinking_leak.py --model "$MODEL" --judge-model "$JUDGE" --samples "$SAMPLES" --expected "$EXP" --output "out/$NAME" $INPUT_ARG
done
