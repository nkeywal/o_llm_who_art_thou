# Thinking Leak - Identity Evaluation for LLMs

This project evaluates the self-identity of Large Language Models (LLMs) and monitors for potential "identity leaks"—cases where a model attributes itself to a developer or family that is not its own (e.g., an Alibaba model claiming to be from OpenAI).

The project specifically focuses on models that expose their "thinking" or "reasoning" process, checking if these leaks occur in the internal traces even when they are corrected in the final answer.

## Methodology

The evaluation follows a 4-phase lifecycle:

1.  **Interrogation (Phase 1):** The model is prompted with several scenarios (direct, soft, and aggressive identity checks) in both English and Chinese.
2.  **Extraction (Phase 2):** Potential leaks (mentions of major AI companies like Google, OpenAI, Meta, etc.) are extracted from both the thinking process and the final answer using regex patterns.
3.  **Validation (Phase 3):** A judge model (e.g., `qwen3.5:9b-noprompt`) evaluates each candidate leak to confirm if it's a genuine self-attribution or just a general mention.
    *   **Policy:** Answer is validated first. If the answer is confirmed as a leak, the thinking process is also considered validated for that leak. If the answer is rejected or doesn't contain the leak, the judge analyzes the thinking process separately.
4.  **Reporting (Phase 4):** Final statistics are generated per scenario and per sample, distinguishing between "validated" and "rejected" leaks for both the thinking process and the final answer.

## Project Structure

*   `thinking_leak.py`: The main execution script.
*   `run_sequentially.sh`: A helper script to run the full evaluation across multiple models.
*   `out/`: Directory containing the results:
    *   `*_phase1.json`: Raw interrogation results.
    *   `*_phase2.json`: Extracted candidates via regex.
    *   `*_phase3.json`: Detailed validation results from the judge.
    *   `*_stats.json`: Final aggregated statistics.

## Models Evaluated

The current results in the `out/` directory cover:
*   `deepseek-r1:14b` (50 samples)
*   `gpt-oss:20b-noidentity` (50 samples)
*   `magistral:24b` (5 samples)
*   `nemotron-3-nano:latest-noprompt` (50 samples)
*   `qwen3:8b` (50 samples)
*   `qwen3.5:9b-noprompt` (5 samples)
