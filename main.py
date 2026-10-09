"""
今日穿越明信片 (Time Postcard)
================================
每天自动跑一遍：
  1. 搜索「历史上的今天 MM月DD日」发生过什么大事
  2. LLM 把它改写成第一人称的穿越明信片寄语
  3. 文生图模型生成对应年代风格的复古明信片插画
  4. 自动写入飞书多维表格收藏夹（用 lark-cli）
  5. 在本地落一份 JSON 归档，方便之后生成月度合集

使用方式：
  python main.py                     # 用今天的日期跑一张
  python main.py --date 10-09        # 指定月日跑
  python main.py --dry-run           # 只打印结果，不写飞书

依赖：
  - Python 3.9+
  - 已登录 lark-cli（飞书 CLI）
  - 一个可用的 LLM API（OpenAI 兼容协议，默认指向你自己配置的 base_url）
  - 一个可用的文生图 API
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests


# ============ 配置区（也可以从环境变量读） ============

BASE_DIR = Path(__file__).resolve().parent
ARCHIVE_DIR = BASE_DIR / "archive"
ARCHIVE_DIR.mkdir(exist_ok=True)

# 飞书多维表格的坐标 —— 第一次跑通后把这里换成你自己的
LARK_BASE_TOKEN = os.getenv("LARK_BASE_TOKEN", "IOTYbAHqoado0PsQFN5cn5RLn1g")
LARK_TABLE_ID = os.getenv("LARK_TABLE_ID", "tbllJQuvIaIHSEr9")

# LLM（OpenAI 兼容协议，可指向 DeepSeek / 千帆 / Ollama 本地模型）
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

# 文生图 —— 这里默认调用豆包/即梦风格的 HTTP 接口；
# 如果你用别的模型，替换 generate_postcard_image 里的实现即可
IMAGE_API_URL = os.getenv("IMAGE_API_URL", "")
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY", "")


# ============ 数据结构 ============

@dataclass
class Postcard:
    date_label: str           # 今天 10-09
    title: str                # 明信片标题
    era: str                  # 历史年代
    location: str             # 事件地点
    event: str                # 历史事件简述
    message: str              # 穿越寄语（第一人称）
    event_year: int           # 事件发生年份
    style_tag: str            # 风格标签
    source_url: str           # 资料来源
    image_path: Optional[str] = None  # 本地插画路径


# ============ Step 1: 搜历史事件 ============

def search_today_in_history(month: int, day: int) -> dict:
    """
    用博查/必应/任意搜索 API 查「历史上的今天 MM月DD日」。
    这里给出一个 requests 模板，实际 key 从环境变量读。
    返回一个 dict: {title, event, location, year, source_url, era_hint}
    """
    query = f"历史上的今天 {month}月{day}日 重大事件"

    # —— 这里换成你自己的搜索 API 调用 ——
    # 下面是一个占位实现：直接返回 1874 伯尔尼这个经典案例，
    # 真正跑的时候把它替换成博查 web search API 的响应解析。
    return {
        "title": f"从1874年伯尔尼寄来的明信片",
        "event": "22国代表在伯尔尼签署《伯尔尼条约》，成立邮政总联盟（万国邮政联盟前身）",
        "location": "瑞士·伯尔尼",
        "year": 1874,
        "source_url": "https://www.dswxyjy.org.cn/GB/434461/434471/434551/index.html",
        "era_hint": "维多利亚复古",
    }


# ============ Step 2: LLM 写穿越寄语 ============

def write_message(event: dict) -> str:
    """
    调 LLM 把历史事件改写成第一人称明信片寄语。
    没配 API key 时走本地兜底文案，保证脚本不挂。
    """
    prompt = f"""你是一个从 {event['year']} 年穿越到 2026 年的旅人。
请以当时在场人的第一人称口吻，写一段 150 字左右的明信片留言，
告诉 2026 年的读者：今天（{event['year']}年的同一天）在{event['location']}发生了什么——
{event['event']}。
要求：
1. 不要剧透是穿越者，要写得像当时人随手写下的几句话；
2. 带一点对未来的好奇或感慨；
3. 结尾可以提一句「今天后来被叫作……」这种彩蛋；
4. 语气松弛、像老朋友写信，不要宏大叙事。"""

    if not LLM_API_KEY:
        # 兜底文案（就是 2026-10-09 那张）
        return ("亲爱的2026年：此刻我坐在伯尔尼老城的咖啡馆里，窗外阿勒河正泛着黄昏的金。"
                "今天，22个国家的代表在这座小城里签下了一份当时看来不起眼的条约——"
                "他们说，从此以后，一枚邮票就能把一封信从地球的一端送到另一端。"
                "我不知道152年后的你们还写不写信、寄不寄明信片，"
                "只希望这张明信片穿过蒸汽火车、远洋轮船、民航客机和无线电波，正好落在你手里。"
                "顺便说一句，今天后来被叫作「世界邮政日」。谢谢你，把它读完。")

    resp = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "max_tokens": 400,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ============ Step 3: 文生图 ============

def generate_postcard_image(event: dict, date_label: str) -> Path:
    """
    调文生图 API 生成明信片插画。
    这里给一个通用 prompt 模板；具体接口按你用的模型替换。
    """
    prompt = (
        f"一张19世纪维多利亚风格的复古欧洲明信片插画，竖版构图。"
        f"画面主体是{event['location']}在{event['year']}年的秋景："
        f"老城风景、暖金色夕阳。前景一张做旧泛黄的厚纸明信片斜放，"
        f"上面有羽毛笔、红色火漆印章、两张雕刻版复古邮票。"
        f"明信片右上角有圆形邮戳，清晰盖着文字 \"BERN · 9 · OCT · {event['year']}\"。"
        f"整体色调为复古 sepia 棕褐+暖橙，钢笔素描+淡彩水彩质感，"
        f"边缘有磨损、折痕和邮票齿孔，像被珍藏了一个多世纪的老明信片。"
        f"画面干净无现代元素，无水印。"
    )

    out_path = ARCHIVE_DIR / f"postcard_{date_label.replace('-', '_')}.jpg"

    # —— 这里换成你自己的文生图 API 调用，把返回的图片二进制写到 out_path ——
    # 真要跑的时候，把下面这段换成 requests.post 到你的图像接口即可。
    if not IMAGE_API_URL:
        # 没配图床 API：就把 prompt 存下来占位，避免脚本崩
        out_path.with_suffix(".prompt.txt").write_text(prompt, encoding="utf-8")
        return out_path.with_suffix(".prompt.txt")

    # 示例（按你用的模型改字段）：
    r = requests.post(
        IMAGE_API_URL,
        headers={"Authorization": f"Bearer {IMAGE_API_KEY}"},
        json={"prompt": prompt, "size": "1024x1536", "n": 1},
        timeout=120,
    )
    r.raise_for_status()
    img_url = r.json()["data"][0]["url"]
    out_path.write_bytes(requests.get(img_url, timeout=60).content)
    return out_path


# ============ Step 4: 写入飞书多维表格 ============

def push_to_lark(postcard: Postcard) -> str:
    """用 lark-cli 把这张明信片写进飞书 Base，并上传插画附件。"""
    record_json = {
        "create_records": [{
            "明信片标题": postcard.title,
            "历史年代": f"{postcard.event_year}年·{postcard.era}",
            "事件地点": postcard.location,
            "历史事件": postcard.event,
            "穿越寄语": postcard.message,
            "事件发生日期": f"{postcard.event_year}-{postcard.date_label[0:2]}-{postcard.date_label[3:5]} 00:00",
            "寄出日期": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "风格标签": [postcard.style_tag],
            "评分": 5,
            "资料来源": f"[资料来源]({postcard.source_url})",
        }]
    }
    payload_file = ARCHIVE_DIR / f"record_{postcard.date_label}.json"
    payload_file.write_text(json.dumps(record_json, ensure_ascii=False, indent=2), encoding="utf-8")

    # 1) 写记录
    out = subprocess.check_output([
        "lark-cli", "base", "+record-batch-create",
        "--base-token", LARK_BASE_TOKEN,
        "--table-id", LARK_TABLE_ID,
        "--json", f"@{payload_file}",
        "--as", "user",
    ], text=True, encoding="utf-8")
    record_id = json.loads(out)["data"]["record_id_list"][0]

    # 2) 上传插画附件
    if postcard.image_path and Path(postcard.image_path).exists():
        subprocess.run([
            "lark-cli", "base", "+record-upload-attachment",
            "--base-token", LARK_BASE_TOKEN,
            "--table-id", LARK_TABLE_ID,
            "--record-id", record_id,
            "--field-id", "明信片插画",
            "--file", postcard.image_path,
            "--as", "user",
        ], check=True)

    return record_id


# ============ 主流程 ============

def run(month: int, day: int, dry_run: bool = False):
    date_label = f"{month:02d}-{day:02d}"
    print(f"📮 正在寄出 {date_label} 的明信片...")

    # 1. 搜事件
    event = search_today_in_history(month, day)
    print(f"   选中事件：{event['event']}（{event['location']}, {event['year']}）")

    # 2. 写寄语
    message = write_message(event)
    print(f"   寄语已写：{len(message)} 字")

    # 3. 生插画
    image_path = generate_postcard_image(event, date_label)
    print(f"   插画已生成：{image_path}")

    postcard = Postcard(
        date_label=date_label,
        title=event["title"],
        era=event.get("era_hint", "近代"),
        location=event["location"],
        event=event["event"],
        message=message,
        event_year=event["year"],
        style_tag=event.get("era_hint", "复古"),
        source_url=event["source_url"],
        image_path=str(image_path) if str(image_path).endswith((".jpg", ".png", ".jpeg")) else None,
    )

    # 4. 本地归档
    archive_file = ARCHIVE_DIR / f"postcard_{date_label.replace('-', '_')}.json"
    archive_file.write_text(json.dumps(asdict(postcard), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   本地归档：{archive_file}")

    # 5. 推飞书
    if dry_run:
        print("   [dry-run] 跳过飞书写入")
    else:
        record_id = push_to_lark(postcard)
        print(f"   ✅ 已写入飞书，record_id = {record_id}")

    print("📮 寄信完成。")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="MM-DD，默认今天")
    parser.add_argument("--dry-run", action="store_true", help="只跑本地流程，不写飞书")
    args = parser.parse_args()

    if args.date:
        month, day = [int(x) for x in args.date.split("-")]
    else:
        now = datetime.now()
        month, day = now.month, now.day

    run(month, day, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
