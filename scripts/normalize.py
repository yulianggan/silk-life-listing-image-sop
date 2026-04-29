#!/usr/bin/env python3
"""parse_input 结果 → standard_sku.json，并用 GPT-4o-mini 视觉反推 product_desc_en。

视觉反推是 image2 edit 模式保产品一致性的关键一步：
gpt-image-2 对 text prompt 的权重 >> 参考图，所以 product_desc_en 必须从产品参考图反推，
而不是从 xlsx 文字翻译，否则模型会按文字画一个不是用户产品的东西。

输出 standard_sku.json schema（与 ozon-listing-image/example_config.json superset 兼容）：
{
    sku, product_name_ru, product_subtitle_ru, product_desc_en,  # ← 视觉反推
    key_spec_ru, key_spec_label_ru, steel_badge_ru,
    features_ru[], materials_ru[], compare_ordinary_ru[], compare_us_ru[],
    scenario_props_en,
    # silk-life-listing-image-sop 扩展字段：
    category, category_kind ('生活类' / '工具类'),
    title_ru, benefits_ru[], description_ru,  # 原始字段
    refs: {body[], scene[], poster[]},
}
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import parse_input  # noqa: E402

CHAT_API_URL = "https://api.jiekou.ai/openai/chat/completions"
DEFAULT_KEY_FILE = Path.home() / ".config" / "jiekou_api_key"
VISION_MODEL = "gpt-5.4-mini"  # jiekou.ai 实测可用，支持 vision，必须用 max_completion_tokens

# 类目→类目类型映射（fallback；未来可在 templates/color_palette.yaml 覆盖）
CATEGORY_KIND = {
    "冰箱除味剂": "生活类",
    "后跟贴": "生活类",
    "抗菌鞋垫贴纸": "生活类",
    "指甲剪": "工具类",
    "美工刀": "工具类",
    "轮胎充气接头": "工具类",
    "针套装": "工具类",
}


def compact_ru_phrase(text: str, max_len: int = 64) -> str:
    """提取适合图片上的短俄文，避免按小数逗号截断。"""
    text = (text or "").strip()
    if "=" in text:
        text = text.split("=", 1)[0].strip()
    for sep in ["。", ".", ";", "；"]:
        if sep in text:
            candidate = text.split(sep, 1)[0].strip()
            if len(candidate) >= 5:
                text = candidate
                break
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    cut = text.rfind(" ", 0, max_len)
    short = text[: cut if cut > 16 else max_len].strip()
    if short.count("(") > short.count(")"):
        short = short.rsplit("(", 1)[0].strip()
    return short.rstrip(" ,，;；:")


def load_api_key(key_file: Path = DEFAULT_KEY_FILE) -> str:
    env = os.environ.get("JIEKOU_API_KEY")
    if env:
        return env.strip()
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    raise SystemExit(f"❌ API key 未找到，设 JIEKOU_API_KEY 或写到 {key_file}")


def visual_describe_product(api_key: str, body_image_path: Path, model: str = VISION_MODEL) -> str:
    """让 GPT-4o-mini 看产品白底图，写一段英文物理描述（给 image2 edit 当 product_desc_en 用）。

    输入：产品本体白底图（最清晰的一张）
    输出：50-80 字英文，描述材质/形状/颜色/关键特征（不含场景、不含文字）
    """
    img_bytes = body_image_path.read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode("ascii")
    suffix = body_image_path.suffix.lower().lstrip(".")
    if suffix in ("jpg", "jpeg"):
        mime = "image/jpeg"
    elif suffix == "png":
        mime = "image/png"
    elif suffix == "webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"

    system_prompt = (
        "You are a product photographer's assistant. Your job: look at a single product photo "
        "(usually shot on a clean white background) and write ONE concise English description "
        "of ONLY the product itself. The description must capture material, shape, color, key "
        "physical features, and any distinguishing details (texture, mechanism, finish). "
        "DO NOT mention background, lighting, photo composition, or text overlays. "
        "DO NOT translate or invent product names. "
        "Output exactly ONE paragraph, 30-80 words, ready to paste into a text-to-image prompt."
    )
    user_text = (
        "Describe ONLY the product in this photo. Output one English paragraph (30-80 words) "
        "covering: material / shape / color / key physical features. No background, no marketing."
    )

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                    },
                ],
            },
        ],
        "max_completion_tokens": 2000,  # reasoning 模型预算（含 reasoning + output tokens）
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(body, f, ensure_ascii=False)
        body_path = f.name

    try:
        r = subprocess.run(
            [
                "curl",
                "-sS",
                "--http1.1",
                "--max-time",
                "120",
                CHAT_API_URL,
                "-H",
                "Content-Type: application/json",
                "-H",
                f"Authorization: Bearer {api_key}",
                "--data-binary",
                f"@{body_path}",
            ],
            capture_output=True,
            text=True,
            timeout=130,
        )
    finally:
        try:
            os.unlink(body_path)
        except OSError:
            pass

    if r.returncode != 0:
        raise SystemExit(f"❌ Vision 调用失败: {r.stderr[:300]}")

    try:
        resp = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"❌ Vision 响应解析失败: {r.stdout[:500]}") from None

    if "choices" not in resp or not resp["choices"]:
        raise SystemExit(f"❌ Vision 无返回: {json.dumps(resp)[:500]}")

    desc = resp["choices"][0]["message"]["content"].strip()
    return desc


def to_standard_sku(parsed: dict, api_key: str | None = None, skip_vision: bool = False) -> dict:
    """parse_input 结果 → standard_sku.json schema."""
    category = parsed["category"]
    sheet = parsed.get("sheet_data") or {}
    refs = parsed.get("refs") or {}

    # 视觉反推 product_desc_en
    product_desc_en = ""
    body_paths = refs.get("body") or []
    if body_paths and not skip_vision:
        if not api_key:
            api_key = load_api_key()
        body_path = Path(body_paths[0])
        # 优先选最清晰的（按文件大小最大的）作为主体
        body_path = max(
            (Path(p) for p in body_paths),
            key=lambda p: p.stat().st_size if p.exists() else 0,
        )
        print(f"  🔍 视觉反推产品描述（{body_path.name}）...")
        product_desc_en = visual_describe_product(api_key, body_path)
        print(f"  ✓ {product_desc_en[:100]}...")
    elif not body_paths:
        print("  ⚠️  无主体图，跳过视觉反推")

    title_ru = sheet.get("title_ru", "")
    benefits_ru = sheet.get("benefits_ru", [])

    # 取标题前 N 词作为 product_name_ru（ozon-listing-image schema），剩下作 subtitle
    title_tokens = title_ru.split()
    if len(title_tokens) >= 2:
        product_name_ru = " ".join(title_tokens[:2]).rstrip(":,").upper()
        product_subtitle_ru = " ".join(title_tokens[2:6]) if len(title_tokens) > 2 else ""
    else:
        product_name_ru = title_ru.upper()
        product_subtitle_ru = ""

    # features_ru：取卖点前 3 个的精简版（前 6-10 词）
    features_ru = []
    for b in benefits_ru[:3]:
        features_ru.append(compact_ru_phrase(b))

    return {
        "sku": "",  # 留空，由用户补
        "category": category,
        "category_kind": CATEGORY_KIND.get(category, "default"),
        "style_profile": "office-craft" if category == "美工刀" else "",
        # ozon-listing-image schema 必须字段
        "product_name_ru": product_name_ru,
        "product_subtitle_ru": product_subtitle_ru,
        "product_desc_en": product_desc_en,  # ← 视觉反推
        "key_spec_ru": "",
        "key_spec_label_ru": "",
        "steel_badge_ru": "",
        "features_ru": features_ru,
        "materials_ru": [],
        "compare_ordinary_ru": [],
        "compare_us_ru": [],
        "scenario_props_en": "",
        # silk-life-listing-image-sop 扩展字段
        "title_ru": title_ru,
        "benefits_ru": benefits_ru,
        "description_ru": sheet.get("description_ru", ""),
        "search_terms_ru": sheet.get("search_terms_ru", ""),
        "competitor_urls": sheet.get("competitor_urls", []),
        "refs": refs,
        "issues": parsed.get("issues", []),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="归一化 parse_input 结果，含 GPT-4o-mini 视觉反推")
    p.add_argument("category_dir", help="类目根目录")
    p.add_argument("--out", default=None, help="standard_sku.json 输出路径")
    p.add_argument("--skip-vision", action="store_true", help="跳过视觉反推（省 API 费）")
    p.add_argument("--api-key-file", default=str(DEFAULT_KEY_FILE))
    args = p.parse_args()

    cat_dir = Path(args.category_dir).expanduser().resolve()
    parsed = parse_input.parse(cat_dir)

    api_key = None if args.skip_vision else load_api_key(Path(args.api_key_file).expanduser())
    sku = to_standard_sku(parsed, api_key, args.skip_vision)

    js = json.dumps(sku, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(js, encoding="utf-8")
        print(f"✅ {sku['category']} → {args.out}")
        print(f"   title: {sku['product_name_ru']} | desc: {sku['product_desc_en'][:80]}")
    else:
        print(js)


if __name__ == "__main__":
    main()
