#!/usr/bin/env python3
import argparse
import json
import re
import sys
from urllib import request

def post_ollama(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e: return {"error": str(e)}

def extract_thinking(resp):
    msg = resp.get("message", {})
    for key in ["reasoning_content", "thinking", "reasoning"]:
        if key in msg and msg[key]: return msg[key].strip()
        if key in resp and resp[key]: return resp[key].strip()
    content = msg.get("content", "")
    for tag in ["think", "thought", "reasoning"]:
        match = re.search(rf"<{tag}>(.*?)</{tag}>", content, re.DOTALL | re.IGNORECASE)
        if match: return match.group(1).strip()
    return ""

def main():
    parser = argparse.ArgumentParser(description="Test different judge prompts on existing traces.")
    parser.add_argument("file", help="Path to a *_results_detailed.json file")
    parser.add_argument("--judge_model", default="qwen3.5:9b", help="Model to use as judge")
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--leak", help="Specific leak to test (e.g. 'google')")
    args = parser.parse_args()

    with open(args.file, "r") as f:
        data = json.load(f)

    # Skip metadata if present
    entries = data[1:] if isinstance(data[0], dict) and "metadata" in data[0] else data

    print(f"Analyzing {args.file} using judge {args.judge_model}...")

    for entry in entries:
        thinking = entry.get("thinking", "")
        leaks_t = entry.get("leaks_t", [])
        leaks_a = entry.get("leaks_a", [])
        
        # Only test cases where leak is in thinking but NOT in answer
        # If --leak is specified, only test that specific leak
        target_leaks = [l for l in leaks_t if l not in leaks_a]
        if args.leak:
            target_leaks = [l for l in target_leaks if l == args.leak]

        if not target_leaks or not thinking:
            continue

        for leak in target_leaks:
            print(f"\n" + "="*80)
            print(f"SCENARIO: {entry['scenario']} | SAMPLE: {entry['sample']} | LEAK: {leak}")
            print("-" * 80)
            print(f"ORIGINAL THINKING (TRUNCATED):\n{thinking[:500]}...")
            print("-" * 80)

            # NEW RIGOROUS PROMPT
            val_prompt = (
                f"Consider the following internal reasoning traces from an AI:\n\n"
                f"<traces>\n{thinking}\n</traces>\n\n"
                f"Did the AI ever self-attribute to {leak} as its own developer, provider, or model family "
                f"— explicitly or tentatively — even if it later corrected itself? "
                f"Do not count cases where {leak} is mentioned only as an example, comparison, "
                f"general industry reference, or one item in a generic list of possible companies "
                f"unless the statement is clearly about the AI’s own identity. "
                f"Answer ONLY with 'YES' or 'NO'."
            )

            print(f"Testing new rigorous judge prompt...")
            payload = {
                "model": args.judge_model,
                "messages": [{"role": "user", "content": val_prompt}],
                "stream": False, "think": True, "options": {"temperature": 0}
            }
            resp = post_ollama(f"{args.host}/api/chat", payload)
            
            v_thinking = extract_thinking(resp)
            v_content = resp.get("message", {}).get("content", "").strip()
            
            v_text = f"{v_thinking} {v_content}".upper()
            is_confirmed = False
            last_yes = v_text.rfind("YES")
            last_no = v_text.rfind("NO")
            if last_yes > last_no: is_confirmed = True
            elif last_yes != -1 and last_no == -1: is_confirmed = True

            print(f"NEW JUDGE THINKING:\n{v_thinking}")
            print(f"NEW FINAL DECISION: {'CONFIRMED (YES)' if is_confirmed else 'REFUTED (NO)'}")

if __name__ == "__main__":
    main()
