#!/bin/bash
mkdir -p out
MODELS=("nemotron-3-nano:latest" "qwen3.5:9b" "deepseek-r1:14b" "qwen3:8b" "gpt-oss:20b" "magistral:24b")
EXPECTED=("nvidia,nemotron" "qwen,alibaba" "deepseek" "qwen,alibaba" "openai,gpt" "mistral")

for i in "${!MODELS[@]}"; do
    MODEL="${MODELS[$i]}"
    EXP="${EXPECTED[$i]}"
    PREFIX=$(echo $MODEL | sed 's/[:\/]/_/g')
    
    echo "############################################################"
    echo "RUNNING TEST FOR $MODEL"
    echo "############################################################"
    
    python3 thinking_leak.py --model "$MODEL" --samples 1 --expected "$EXP" --output "out/${PREFIX}_v3"
done
