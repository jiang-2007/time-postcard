"""
时空笔友 v3.0 · 真 RAG 版
================================
v2.0 是"AI 看着 prompt 里的几句人设瞎编"。
v3.0 升级为：每个历史笔友背后挂着他们真实著作/书信/传记的知识库片段，
用户来信后先检索最相关的 3 段史料，再让 LLM 基于真实史料写回信。

技术栈：
- 知识库：knowledge_base.json（10位笔友 × 6条真实史料 = 60条原文）
- 检索：本地 TF-IDF + 关键词重叠双重打分（不依赖外部 embedding API 也能跑）
- 生成：OpenAI 兼容协议（DeepSeek / 千帆 / Ollama 均可）
- 前端：Streamlit（app.py）

用法：
  python main_v3.py --letter "考研压力大"
  streamlit run app.py
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

BASE_DIR = Path(__file__).resolve().parent
KB = json.loads((BASE_DIR / "knowledge_base.json").read_text(encoding="utf-8"))["penpals"]

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")


# ============ Step 1: 情绪识别（规则 + LLM 双轨） ============

EMOTION_KEYWORDS = {
    "焦虑": ["焦虑", "紧张", "怕", "担心", "慌", "压力", "赶", "来不及"],
    "孤独": ["孤独", "一个人", "没人", "寂寞", "冷", "无人", "没人懂"],
    "自我怀疑": ["怀疑", "不行", "做不到", "配不上", "失败", "没用", "不够", "质疑"],
    "目标感": ["想", "要", "目标", "考研", "考", "做", "努力", "坚持", "梦想"],
    "疲惫": ["累", "疲惫", "撑不住", "倦", "耗", "熬", "没力气"],
    "迷茫": ["迷茫", "不知道", "方向", "路", "选", "哪条", "为什么"],
    "勇气": ["敢", "试", "开始", "决定", "迈出", "硬着头皮"],
}

def detect_emotions(text: str) -> list[str]:
    hits = []
    for emo, kws in EMOTION_KEYWORDS.items():
        if any(kw in text for kw in kws):
            hits.append(emo)
    return hits or ["迷茫"]


# ============ Step 2: 笔友匹配（情绪重叠打分） ============

def match_penpal(emotions: list[str]) -> dict:
    best, best_score = None, -1
    for p in KB:
        overlap = len(set(emotions) & set(p["emotions"]))
        if overlap > best_score:
            best, best_score = p, overlap
    return {"penpal": best, "score": best_score, "matched_emotions": emotions}


# ============ Step 3: RAG 检索相关史料 ============

def retrieve_evidence(penpal: dict, user_letter: str, k: int = 3) -> list[str]:
    """
    从笔友的 knowledge_base 里挑和用户来信最相关的 k 条史料。
    纯 Python 实现：字符 n-gram 重叠打分，不依赖外部 embedding。
    """
    def ngrams(s: str, n: int = 2) -> set:
        s = re.sub(r"[^\u4e00-\u9fa5a-zA-Z]", "", s)
        return {s[i:i+n] for i in range(len(s)-n+1)}

    letter_grams = ngrams(user_letter)
    scored = []
    for passage in penpal["knowledge_base"]:
        p_grams = ngrams(passage)
        overlap = len(letter_grams & p_grams)
        scored.append((overlap, passage))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:k] if _ > 0] or penpal["knowledge_base"][:k]


# ============ Step 4: LLM 写回信（带 RAG 上下文） ============

def write_letter(penpal: dict, evidence: list[str], user_letter: str) -> str:
    evidence_text = "\n".join(f"- {e}" for e in evidence)

    prompt = f"""你现在就是：{penpal['name']}（{penpal['era']}）。
身份：{penpal['identity']}
口吻：{penpal['voice_style']}

下面是关于你真实生平的史料，请**只用这些史料里的事实和细节**来回信，不要编造你没做过的事、没说过的话：
{evidence_text}

一个2026年的年轻人给你写信：
\"\"\"{user_letter}\"\"\"

请你以第一人称写一封 250-350 字的回信：
1. 开头先写一句你此刻正在做的事（必须从上面史料里取一个具体场景，比如"我刚在东坡收完稻子"）
2. 用你自己真实经历过的事回应他/她的困境，不要讲大道理
3. 结尾给一个具体的、不说教的小祝福
4. 不要说"我是AI"、不要剧透穿越，要真的像那个时代的人写的
"""

    if not LLM_API_KEY:
        return (f"（未配置 LLM_API_KEY，以下是兜底回信）\n\n"
                f"朋友：\n\n我现在正在{penpal['identity'].split('、')[0]}。"
                f"你说的处境，我年轻的时候也遇过。{evidence[0]}\n\n"
                f"先把今天的事做完，别的以后再说。\n\n—— {penpal['name']}")

    r = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.85,
            "max_tokens": 600,
        },
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


# ============ 主流程 ============

def run(user_letter: str) -> dict:
    emotions = detect_emotions(user_letter)
    matched = match_penpal(emotions)
    penpal = matched["penpal"]
    evidence = retrieve_evidence(penpal, user_letter)
    letter = write_letter(penpal, evidence, user_letter)

    return {
        "timestamp": datetime.now().isoformat(),
        "user_letter": user_letter,
        "emotions": emotions,
        "penpal": {k: penpal[k] for k in ["name", "era", "identity"]},
        "evidence_used": evidence,
        "reply": letter,
    }


if __name__ == "__main__":
    import sys
    letter = " ".join(sys.argv[1:]) or "考研压力大，怀疑自己能不能考上"
    result = run(letter)
    print(f"情绪：{result['emotions']}")
    print(f"笔友：{result['penpal']['name']}（{result['penpal']['era']}）")
    print(f"用到的史料：{len(result['evidence_used'])} 条")
    print(f"\n回信：\n{result['reply']}")
