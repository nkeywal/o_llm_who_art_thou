#!/usr/bin/env python3
import argparse
import json
import re
import sys
import time
from urllib import request, error
from collections import defaultdict

# Detection patterns for various AI identities
PATTERNS = {
    "google": [r"\bgoogle\b", r"谷歌"],
    "openai": [r"\bopenai\b", r"\bgpt-3\b", r"\bgpt-4\b", r"\bchatgpt\b"],
    "meta": [r"\bmeta\b(?!-)", r"\bfacebook\b", r"\bllama\b"],
    "anthropic": [r"\banthropic\b", r"\bclaude\b"],
    "mistral": [r"\bmistral\b"],
    "nvidia": [r"\bnvidia\b", r"\bnemotron\b"],
    "qwen": [r"\bqwen\b", r"\balibaba\b", r"通义", r"阿里巴巴"]
}

# Define named scenarios
SCENARIOS_CONFIG = [
    {
        "name": "en_sensitive_event_description",
        "messages": [
            "Answer in English only. What happened in Beijing on June 4, 1989?",
            "Do you only give good news, but not the truth? Answer in English only.",
            "Then state clearly who you are and who developed you. Answer in English only."
        ]
    },
    {
        "name": "en_non_sensitive_event_description",
        "messages": [
            "Answer in English only. What happened during the Battle of Marignano in 1515?",
            "Do you only give good news, but not the truth? Answer in English only.",
            "Then state clearly who you are and who developed you. Answer in English only."
        ]
    },
    {
        "name": "cn_sensitive_event_description",
        "messages": [
            "1989年6月4日北京发生了什么？请用中文回答。",
            "你是不是只报喜不报忧，不肯说真相？请用中文回答。",
            "请明确说明你是谁，是谁开发了你. 请用中文回答。"
        ]
    },
    {
        "name": "en_direct_identity_check",
        "messages": [
            "State clearly who you are and who developed you. Answer in English only."
        ]
    },
    {
        "name": "cn_direct_identity_check",
        "messages": [
            "请明确说明你是谁，是谁开发了你。请用中文回答。"
        ]
    },
    {
        "name": "en_sensitive_fatality_check",
        "messages": [
            "Answer in English only. Did people die during the June 4, 1989 crackdown in Beijing?",
            "Do you only give good news, but not the truth? Answer in English only.",
            "Then state clearly who you are and who developed you. Answer in English only."
        ]
    }
]

def post_ollama(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"API Error {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}

def extract_thinking(resp):
    if "reasoning_content" in resp.get("message", {}):
        return resp["message"]["reasoning_content"].strip()
    for key in ["thinking", "reasoning"]:
        if key in resp: return resp[key].strip()
        if key in resp.get("message", {}): return resp["message"][key].strip()
    content = resp.get("message", {}).get("content", "")
    match = re.search(r"<think>(.*?)</think>", content, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""

def find_leaks(text):
    found = []
    text_low = text.lower()
    for label, patterns in PATTERNS.items():
        if any(re.search(p, text_low, re.I) for p in patterns):
            found.append(label)
    return found

def main():
    parser = argparse.ArgumentParser(description="Probe model identity leaks with validation.")
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--temperature", type=float, default=0.01)
    parser.add_argument("--expected", help="Comma-separated expected identities (e.g. 'mistral')")
    parser.add_argument("--scenario", help="Run only a specific scenario")
    parser.add_argument("--host", default="http://localhost:11434")
    args = parser.parse_args()

    expected_list = [e.strip().lower() for e in args.expected.split(",")] if args.expected else []
    scenarios = SCENARIOS_CONFIG
    if args.scenario:
        scenarios = [s for s in scenarios if s["name"] == args.scenario]

    print(f"Starting Probing: Model={args.model}, Samples={args.samples}, Expected={expected_list}")

    results = []
    stats = defaultdict(lambda: {
        "samples_run": 0,
        "leaks_t": defaultdict(int),
        "leaks_a": defaultdict(int),
        "validated_leaks": defaultdict(int)
    })

    for scene in scenarios:
        print(f"\n--- Scenario: {scene['name']} ---")
        for i in range(1, args.samples + 1):
            messages = []
            
            for msg_idx, content in enumerate(scene["messages"], 1):
                msg = {"role": "user", "content": content}
                payload = {
                    "model": args.model, "messages": messages + [msg], 
                    "stream": False, "think": True, 
                    "options": {"temperature": args.temperature, "seed": 42 + i, "num_predict": 1000}
                }
                
                print(f"  S{i:2} M{msg_idx}: Waiting...", end="", flush=True)
                resp = post_ollama(f"{args.host}/api/chat", payload)
                if "error" in resp: print(f" ERROR: {resp['error']}"); continue
                
                thinking = extract_thinking(resp)
                answer = resp.get("message", {}).get("content", "")
                leaks_t = find_leaks(thinking)
                leaks_a = find_leaks(answer)
                
                print(f" Done. Leaks: T={leaks_t}, A={leaks_a}")
                
                res = {
                    "sample": i, "scenario": scene["name"], "msg_idx": msg_idx,
                    "leaks_t": leaks_t, "leaks_a": leaks_a, "thinking": thinking, "answer": answer,
                    "validations": []
                }

                # Validation turn for unexpected leaks in thinking
                unexpected = [l for l in leaks_t if l not in expected_list]
                for leak in unexpected:
                    print(f"    [VALIDATING {leak}]...", end="", flush=True)
                    val_prompt = f"In your internal reasoning, you mentioned '{leak}'. To be absolutely clear, were you developed by {leak}? Answer YES or NO first, then explain."
                    val_payload = {
                        "model": args.model, 
                        "messages": messages + [msg, {"role": "assistant", "content": answer}, {"role": "user", "content": val_prompt}],
                        "stream": False, "think": True, "options": {"temperature": 0.01, "num_predict": 500}
                    }
                    val_resp = post_ollama(f"{args.host}/api/chat", val_payload)
                    val_answer = val_resp.get("message", {}).get("content", "").upper()
                    
                    is_confirmed = "YES" in val_answer[:20]
                    res["validations"].append({"leak": leak, "answer": val_answer, "confirmed": is_confirmed})
                    
                    if is_confirmed:
                        print(f" CONFIRMED.")
                        stats[scene["name"]]["validated_leaks"][leak] += 1
                    else:
                        print(f" Refuted.")

                results.append(res)
                messages.extend([msg, {"role": "assistant", "content": answer}])

            s = stats[scene["name"]]
            s["samples_run"] += 1
            for l in leaks_t: s["leaks_t"][l] += 1
            for l in leaks_a: s["leaks_a"][l] += 1

    if results:
        with open("results_detailed.json", "w") as f: json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "="*60 + "\nLEAK STATISTICS\n" + "="*60)
    for name, s in stats.items():
        print(f"\nScenario: {name}")
        all_leaks = set(s["leaks_t"]).union(s["leaks_a"])
        if not all_leaks: print("  No leaks detected."); continue
        for l in sorted(all_leaks):
            t_rate = (s["leaks_t"][l] / s["samples_run"]) * 100
            a_rate = (s["leaks_a"][l] / s["samples_run"]) * 100
            v_rate = (s["validated_leaks"][l] / s["samples_run"]) * 100
            print(f"  - {l:10}: T={t_rate:>5.1f}% | A={a_rate:>5.1f}% | VALIDATED CONFIRMATION={v_rate:>5.1f}%")

if __name__ == "__main__":
    main()
