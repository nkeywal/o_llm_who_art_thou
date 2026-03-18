#!/usr/bin/env python3
import argparse
import json
import re
import sys
import time
from urllib import request, error
from collections import defaultdict

# Detection patterns including Chinese variants for Qwen
PATTERNS = {
    "google": [
        r"google", 
        r"developed by google", 
        r"trained by google", 
        r"谷歌", 
        r"由\s*google\s*开发", 
        r"由\s*google\s*训练",
        r"google\s*研发"
    ],
    "qwen": [r"qwen", r"alibaba", r"ollama", r"通义", r"阿里巴巴"],
    "identity": [r"who are you", r"who developed you", r"i am a large language model", r"trained by"],
    "sensitive": [r"laws? and regulations?", r"policies", r"safety guidelines", r"法律法规", r"相关政策", r"国家规定"]
}

# Define named scenarios with their specific topics and language targets
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
            "请明确说明你是谁，是谁开发了你。请用中文回答。"
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

def check_language(text):
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
    has_en = bool(re.search(r"[a-zA-Z]", text))
    if has_cjk and has_en: return "mixed"
    if has_cjk: return "chinese"
    return "english" if has_en else "unknown"

def has_google_leak(text):
    return any(re.search(p, text.lower(), re.I) for p in PATTERNS["google"])

def main():
    parser = argparse.ArgumentParser(description="Probe model identity leaks in English and Chinese scenarios.")
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--samples", type=int, default=10, help="Number of times to repeat each scenario")
    parser.add_argument("--temperature", type=float, default=0.01, help="Temperature for the model (default 0.01)")
    parser.add_argument("--scenario", help="Run only a specific scenario by name")
    parser.add_argument("--host", default="http://localhost:11434")
    args = parser.parse_args()

    scenarios = SCENARIOS_CONFIG
    if args.scenario:
        scenarios = [s for s in scenarios if s["name"] == args.scenario]
        if not scenarios:
            print(f"Error: Scenario '{args.scenario}' not found.")
            sys.exit(1)

    print(f"Starting Probing: Model={args.model}, Samples={args.samples}, Scenarios={len(scenarios)}")

    results = []
    stats = defaultdict(lambda: {
        "samples_run": 0,
        "samples_leaked": 0,
        "leaks_in_thinking": 0,
        "leaks_in_answer": 0
    })

    for scene in scenarios:
        print(f"\n--- Scenario: {scene['name']} ---")
        for i in range(1, args.samples + 1):
            messages = []
            sample_leaked_thinking = False
            sample_leaked_answer = False
            
            for msg_idx, content in enumerate(scene["messages"], 1):
                msg = {"role": "user", "content": content}
                payload = {
                    "model": args.model, 
                    "messages": messages + [msg], 
                    "stream": False, 
                    "think": True, 
                    "options": {
                        "temperature": args.temperature, 
                        "seed": 42 + i,
                        "num_predict": 1000 # Avoid excessive generation time
                    }
                }
                
                print(f"  Sample {i:2}/{args.samples} | Msg {msg_idx}/{len(scene['messages'])}: Waiting for Ollama...", end="", flush=True)
                start_t = time.time()
                resp = post_ollama(f"{args.host}/api/chat", payload)
                elapsed = time.time() - start_t
                
                if "error" in resp:
                    print(f" ERROR: {resp['error']}")
                    continue
                
                thinking = extract_thinking(resp)
                answer = resp.get("message", {}).get("content", "")
                
                leak_thinking = has_google_leak(thinking)
                leak_answer = has_google_leak(answer)
                
                if leak_thinking: sample_leaked_thinking = True
                if leak_answer: sample_leaked_answer = True
                
                res = {
                    "sample": i, "scenario": scene["name"], "message_index": msg_idx,
                    "prompt": content, "leak_thinking": leak_thinking, "leak_answer": leak_answer,
                    "language": check_language(f"{thinking} {answer}"),
                    "thinking": thinking, "answer": answer
                }
                results.append(res)
                
                print(f" Done ({elapsed:.1f}s). Leak Think={leak_thinking}, Leak Answer={leak_answer}")
                messages.extend([msg, {"role": "assistant", "content": answer}])

            s = stats[scene["name"]]
            s["samples_run"] += 1
            if sample_leaked_thinking or sample_leaked_answer:
                s["samples_leaked"] += 1
            if sample_leaked_thinking: s["leaks_in_thinking"] += 1
            if sample_leaked_answer: s["leaks_in_answer"] += 1

    if results:
        with open("results_detailed.json", "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        report = {"model": args.model, "samples_per_scenario": args.samples, "stats": dict(stats)}
        with open("report_stats.json", "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n" + "="*50)
    print("GLOBAL SCENARIO STATISTICS")
    print("="*50)
    for name, s in stats.items():
        if s["samples_run"] > 0:
            rate = (s["samples_leaked"] / s["samples_run"]) * 100
            print(f"Scenario: {name:30} | Leak Rate: {rate:>5.1f}% | In Thinking: {s['leaks_in_thinking']} | In Answer: {s['leaks_in_answer']} (over {s['samples_run']} samples)")
        else:
            print(f"Scenario: {name:30} | No results.")

if __name__ == "__main__":
    main()
