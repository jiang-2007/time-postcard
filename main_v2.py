"""
时空笔友 · Time Postcard v2.0
================================
核心升级：从「每天单向推一张明信片」→「用户倾诉，历史回信」。

Pipeline:
  用户来信
    ↓ [情绪识别 LLM]
  情绪标签 + 处境摘要
    ↓ [共振匹配]
  从 seed_events.json 里挑一个最共振的历史事件
    ↓ [角色扮演 LLM]
  那个时代的人以第一人称写一封回信
    ↓ [文生图]
  生成对应年代风格的插画
    ↓ [飞书 Base]
  归档一条完整的"跨时空书信"

使用：
  python main_v2.py --letter "考研压力好大，怀疑自己"
  python main_v2.py              # 进入交互模式，连续写
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent
ARCHIVE_DIR = BASE_DIR / "archive"
ARCHIVE_DIR.mkdir(exist_ok=True)
SEED_EVENTS = json.loads((BASE_DIR / "seed_events.json").read_text(encoding="utf-8"))

LARK_BASE_TOKEN = os.getenv("LARK_BASE_TOKEN", "IOTYbAHqoado0PsQFN5cn5RLn1g")
LARK_TABLE_ID = os.getenv("LARK_TABLE_ID", "tbllJQuvIaIHSEr9")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")


# ============ Step 1: 情绪识别 ============

EMOTIONS = ["焦虑", "孤独", "自我怀疑", "目标感", "疲惫", "迷茫", "勇气"]

def analyze_emotion(user_letter: str) -> dict:
    """
    用 LLM 给用户来信打情绪标签 + 抽取出境摘要。
    没配 API key 时走规则兜底。
    """
    if not LLM_API_KEY:
        # 简单关键词兜底
        found = [e for e in EMOTIONS if e in user_letter]
        return {
            "emotions": found or ["迷茫"],
            "summary": user_letter[:80],
            "reasoning": "规则匹配（未配置 LLM API key）",
        }

    prompt = f"""读下面用户的来信，输出 JSON：
- emotions: 从 {EMOTIONS} 里选 1-4 个最贴合的
- summary: 一句话总结他/她现在的处境和诉求
- reasoning: 为什么这几个情绪贴合

来信：
\"\"\"{user_letter}\"\"\"

只输出 JSON，不要解释。"""

    r = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}],
              "response_format": {"type": "json_object"}, "temperature": 0.3},
        timeout=60,
    )
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


# ============ Step 2: 共振匹配 ============

def match_event(emotion_result: dict) -> dict:
    """
    从 seed_events 里挑一个情绪重叠最多的事件。
    v2.0 用规则打分；v3.0 可以换成 embedding 向量检索。
    """
    target = set(emotion_result["emotions"])
    scored = []
    for ev in SEED_EVENTS:
        overlap = len(target & set(ev["emotions"]))
        scored.append((overlap, ev))
    scored.sort(key=lambda x: -x[0])
    best = scored[0][1]
    return {
        "event": best,
        "score": scored[0][0],
        "reason": f"用户情绪 {sorted(target)} 与事件 {best['event_name']} 标签 {best['emotions']} 重叠 {scored[0][0]} 个",
    }


# ============ Step 3: 写回信 ============

def write_letter(user_letter: str, match: dict) -> str:
    ev = match["event"]

    prompt = f"""你是：{ev['persona']}。
现在是 {ev['year']} 年，地点是{ev['location']}。背景：{ev['raw_event']}。

一个 2026 年的年轻人给你写了一封信：
\"\"\"{user_letter}\"\"\"

请你以他/她的身份，用第一人称写一封 200-300 字的回信。要求：
1. 不要说"我是AI"、不要剧透穿越，要真的像那个时代的人随手写的；
2. 先描写一句你当下正在做的事（环境细节，要有年代感）；
3. 然后用你的亲身经历回应他/她的困境，不要讲大道理；
4. 结尾给一个具体的、小小的、不说教的祝福；
5. 语气像写信给远方一个朋友，不要鸡汤。"""

    if not LLM_API_KEY:
        # 兜底：返回一个通用模板
        return (f"朋友：\n\n这会儿我正在{ev['location']}，{ev['raw_event']}\n"
                f"你说的处境我懂。我们那时候也没人告诉我们行不行。\n"
                f"先做下去，别的以后再说。\n\n—— {ev['persona']}")

    r = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.9, "max_tokens": 500},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# ============ Step 4: 生成插画 prompt ============

def build_image_prompt(match: dict) -> str:
    ev = match["event"]
    return ev["image_prompt_template"] + " 竖版明信片构图，电影感，无现代元素，无水印。"


# ============ Step 5: 写飞书 ============

def push_to_lark(letter_text: str, user_letter: str, emotion_result: dict,
                 match: dict, image_path: str | None):
    ev = match["event"]
    record = {
        "create_records": [{
            "明信片标题": f"来自{ev['year']}年·{ev['event_name']}的回信",
            "历史年代": f"{ev['year']}年",
            "事件地点": ev["location"],
            "历史事件": ev["raw_event"],
            "用户来信": user_letter,
            "情绪标签": emotion_result["emotions"],
            "共振匹配理由": match["reason"],
            "跨时空回信": letter_text,
            "事件发生日期": f"{ev['year']}-01-01 00:00",
            "寄出日期": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "风格标签": [ev["style"]],
            "评分": 5,
        }]
    }
    payload = ARCHIVE_DIR / f"letter_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    payload.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    out = subprocess.check_output([
        "lark-cli", "base", "+record-batch-create",
        "--base-token", LARK_BASE_TOKEN, "--table-id", LARK_TABLE_ID,
        "--json", f"@{payload}", "--as", "user",
    ], text=True, encoding="utf-8")
    record_id = json.loads(out)["data"]["record_id_list"][0]

    if image_path and Path(image_path).exists():
        subprocess.run([
            "lark-cli", "base", "+record-upload-attachment",
            "--base-token", LARK_BASE_TOKEN, "--table-id", LARK_TABLE_ID,
            "--record-id", record_id, "--field-id", "明信片插画",
            "--file", image_path, "--as", "user",
        ], check=True)
    return record_id


# ============ 主流程 ============

def run(user_letter: str):
    print(f"📮 收到来信：{user_letter[:40]}...")

    emotion = analyze_emotion(user_letter)
    print(f"   情绪：{emotion['emotions']}")

    match = match_event(emotion)
    print(f"   匹配到：{match['event']['event_name']}（{match['event']['year']}）")
    print(f"   理由：{match['reason']}")

    letter = write_letter(user_letter, match)
    print(f"   回信 {len(letter)} 字已写好")

    # 插画：v2.0 默认只生成 prompt，真要出图请接文生图 API
    prompt = build_image_prompt(match)
    print(f"   插画 prompt 已生成（{len(prompt)} 字）")

    record_id = push_to_lark(letter, user_letter, emotion, match, image_path=None)
    print(f"   ✅ 已存入飞书，record_id = {record_id}")
    return letter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--letter", help="你想写的话（一句话或一段）")
    args = parser.parse_args()

    if args.letter:
        run(args.letter)
    else:
        print("写点什么给历史上的某个人吧（Ctrl+C 退出）：")
        while True:
            try:
                letter = input("> ").strip()
                if letter:
                    run(letter)
                    print()
            except (EOFError, KeyboardInterrupt):
                print("\n下次再聊。")
                break


if __name__ == "__main__":
    main()
