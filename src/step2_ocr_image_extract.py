# -*- coding: utf-8 -*-
"""
步骤2: OCR文本提取 + 图片提取与对齐
1. 对每页PDF进行OCR,提取正文文本
2. 提取PDF中的图片,尽量裁切到火炮主图而不是整页扫描图
3. 基于规则从OCR文本中提取基本参数(口径/射程/重量/射速等)
"""
import fitz
import io
import json
import os
import sys
import re
import hashlib
import numpy as np
import cv2
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding='utf-8')

PDF_PATH = "../book/全球火炮鉴赏指南（珍藏版） -- 《深度军事》 编委会 -- 世界军事鉴赏指南系列, 2018 -- 清华大学出版社.pdf"
OUTPUT_DIR = "../data/output"
IMAGE_DIR = "../data/images"
IMAGES_ONLY = os.environ.get("IMAGES_ONLY", "0") == "1"

# 基本参数正则
PARAM_PATTERNS = {
    "caliber": r'口径[：:\s]*(\d+)\s*毫米',
    "length": r'全长[：:\s]*([\d.]+)\s*米',
    "barrel_length": r'炮管长[：:\s]*([\d.]+)\s*米',
    "width": r'全宽[：:\s]*([\d.]+)\s*米',
    "height": r'全高[：:\s]*([\d.]+)\s*米',
    "weight": r'重量[：:\s]*([\d,]+)\s*千克',
    "rate_of_fire": r'(?:最大)?射速[：:\s]*([\d]+)\s*发[／/]分',
    "range": r'(?:有效)?射程[：:\s]*([\d,]+)\s*米',
}


def ocr_all_pages(doc, start_page=12, end_page=367):
    """OCR提取所有武器页面的文本"""
    ocr = RapidOCR()
    page_texts = {}

    for pg_idx in range(start_page - 1, min(end_page, doc.page_count)):
        page = doc[pg_idx]
        pix = page.get_pixmap(dpi=200)
        tmp_path = os.path.join(OUTPUT_DIR, f"_tmp_p{pg_idx+1}.png")
        pix.save(tmp_path)

        result, _ = ocr(tmp_path)
        if result:
            text_lines = [line[1] for line in result]
            full_text = "\n".join(text_lines)
            page_texts[pg_idx + 1] = full_text
        else:
            page_texts[pg_idx + 1] = ""

        if pg_idx % 20 == 0:
            print(f"  OCR进度: {pg_idx+1}/{end_page}")

    for f in os.listdir(OUTPUT_DIR):
        if f.startswith("_tmp_p") and f.endswith(".png"):
            os.remove(os.path.join(OUTPUT_DIR, f))

    return page_texts


def _score_bbox(page_rect, bbox):
    """给候选图片区域打分，偏好页面中部的横向大图，惩罚整页扫描图。"""
    x0, y0, x1, y1 = bbox
    width = max(x1 - x0, 1)
    height = max(y1 - y0, 1)
    area = width * height
    page_area = page_rect.width * page_rect.height
    area_ratio = area / page_area
    center_y = (y0 + y1) / 2 / page_rect.height
    aspect = width / height

    if width < page_rect.width * 0.18 or height < page_rect.height * 0.10:
        return -1
    if area_ratio > 0.88:
        return -1

    score = area_ratio * 100
    if 0.18 <= center_y <= 0.78:
        score += 20
    if 1.0 <= aspect <= 3.8:
        score += 10
    if y0 < page_rect.height * 0.08:
        score -= 8
    if y1 > page_rect.height * 0.92:
        score -= 8
    return score


def _extract_image_block_candidates(page):
    """优先从PDF版面中的图片块找候选区域。"""
    candidates = []
    page_dict = page.get_text("dict")
    for block in page_dict.get("blocks", []):
        if block.get("type") != 1:
            continue
        bbox = block.get("bbox")
        if not bbox:
            continue
        score = _score_bbox(page.rect, bbox)
        if score < 0:
            continue
        candidates.append({
            "bbox": bbox,
            "score": score,
            "source": "image_block",
        })
    return candidates


def _find_dense_band(values, min_len, threshold_ratio):
    max_value = max(values) if values else 0
    if max_value <= 0:
        return None
    threshold = max_value * threshold_ratio
    start = None
    best = None
    for idx, value in enumerate(values):
        if value >= threshold:
            if start is None:
                start = idx
        else:
            if start is not None:
                end = idx - 1
                if end - start + 1 >= min_len:
                    if best is None or (end - start) > (best[1] - best[0]):
                        best = (start, end)
                start = None
    if start is not None:
        end = len(values) - 1
        if end - start + 1 >= min_len:
            if best is None or (end - start) > (best[1] - best[0]):
                best = (start, end)
    return best


def _crop_main_visual_from_page(page):
    """
    当PDF内部只有整页扫描图时，退化为对整页做版面分析，
    尽量截出最大的“照片区域”，而不是文字+参数表混合区域。
    """
    pix = page.get_pixmap(dpi=160, alpha=False)
    pil_rgb = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    img = np.array(pil_rgb)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape

    # 非白区域
    content_mask = (gray < 242).astype(np.uint8) * 255
    # 闭运算把照片内部空洞填起来，形成大块区域
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (31, 31))
    closed = cv2.morphologyEx(content_mask, cv2.MORPH_CLOSE, kernel)
    # 开运算去掉细碎文字噪声
    opened = cv2.morphologyEx(
        closed,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)),
    )

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)

    best_box = None
    best_score = -1
    for label in range(1, num_labels):
        x, y, w, h, area = stats[label]
        area_ratio = area / float(width * height)
        aspect = w / max(h, 1)

        if w < width * 0.22 or h < height * 0.08:
            continue
        if area_ratio < 0.03:
            continue
        if y > height * 0.78:
            continue

        roi = img[y:y+h, x:x+w]
        variance = float(np.std(roi))

        score = area_ratio * 100
        if 1.1 <= aspect <= 3.8:
            score += 18
        if y < height * 0.58:
            score += 20
        if variance > 28:
            score += 18
        elif variance > 18:
            score += 8
        if w > width * 0.45:
            score += 8
        if h > height * 0.12:
            score += 8
        if x < width * 0.04 or (x + w) > width * 0.96:
            score -= 6
        if y < height * 0.05:
            score -= 6

        if score > best_score:
            best_score = score
            best_box = (x, y, w, h)

    if best_box is not None:
        x, y, w, h = best_box
        pad_x = int(w * 0.02)
        pad_y = int(h * 0.03)
        x0 = max(0, x - pad_x)
        y0 = max(0, y - pad_y)
        x1 = min(width, x + w + pad_x)
        y1 = min(height, y + h + pad_y)
        return pil_rgb.crop((x0, y0, x1, y1)), "page_photo_component"

    # 回退方案：用之前的密度裁剪
    rows = (gray < 235).sum(axis=1).tolist()
    row_band = _find_dense_band(rows, min_len=max(120, height // 8), threshold_ratio=0.34)
    if not row_band:
        return pil_rgb.crop((0, int(height * 0.16), width, int(height * 0.68))), "page_density_fallback"

    y0, y1 = row_band
    y0 = max(0, y0 - 20)
    y1 = min(height, y1 + 20)
    cols = (gray[y0:y1, :] < 235).sum(axis=0).tolist()
    col_band = _find_dense_band(cols, min_len=max(120, width // 5), threshold_ratio=0.22)
    if not col_band:
        x0, x1 = int(width * 0.08), int(width * 0.92)
    else:
        x0, x1 = col_band
        x0 = max(0, x0 - 20)
        x1 = min(width, x1 + 20)
    return pil_rgb.crop((x0, y0, x1, y1)), "page_density_crop"


def _render_bbox_crop(page, bbox, dpi=220):
    rect = fitz.Rect(bbox)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png")))


def extract_images_from_pdf(doc, toc_data):
    """提取PDF中的武器图片，尽量只保留火炮主体图。"""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    image_map = {}
    image_meta = {}

    page_to_weapon = {}
    for art in toc_data["artillery"]:
        page_to_weapon[art["page"]] = art["name"]

    for page_num, weapon_name in page_to_weapon.items():
        pg_idx = page_num - 1
        if pg_idx >= doc.page_count:
            continue

        page = doc[pg_idx]
        page_rect = page.rect
        candidates = _extract_image_block_candidates(page)

        best_image = None
        method = ""
        bbox = None

        if candidates:
            best = sorted(candidates, key=lambda item: item["score"], reverse=True)[0]
            bbox = best["bbox"]
            try:
                best_image = _render_bbox_crop(page, bbox)
                method = best["source"]
            except Exception:
                best_image = None

        if best_image is None:
            try:
                best_image, method = _crop_main_visual_from_page(page)
                bbox = None
            except Exception:
                best_image = None

        if best_image is None:
            continue

        # 用hash生成安全文件名，统一转JPEG
        name_hash = hashlib.md5(weapon_name.encode("utf-8")).hexdigest()[:12]
        img_path = os.path.join(IMAGE_DIR, f"artillery_{name_hash}.jpeg")
        rgb_img = best_image.convert("RGB")
        rgb_img.save(img_path, format="JPEG", quality=92)
        image_map[weapon_name] = img_path

        image_meta[weapon_name] = {
            "page": page_num,
            "method": method,
            "size": list(rgb_img.size),
            "page_size": [page_rect.width, page_rect.height],
            "bbox": list(bbox) if bbox else None,
        }

    return image_map, image_meta


def extract_parameters_from_text(weapon_name, text):
    """从OCR文本中用正则提取武器基本参数"""
    params = {}
    for param_key, pattern in PARAM_PATTERNS.items():
        m = re.search(pattern, text)
        if m:
            params[param_key] = m.group(1).replace(",", "")
    return params


def assign_texts_to_weapons(page_texts, toc_data):
    """将OCR文本按页码范围分配给各武器"""
    artillery = sorted(toc_data["artillery"], key=lambda x: x["page"])

    weapon_texts = {}
    for i, art in enumerate(artillery):
        start_page = art["page"]
        if i + 1 < len(artillery):
            end_page = artillery[i + 1]["page"] - 1
        else:
            end_page = 367

        combined_text = []
        for pg in range(start_page, end_page + 1):
            if str(pg) in page_texts or pg in page_texts:
                t = page_texts.get(pg, page_texts.get(str(pg), ""))
                if t:
                    combined_text.append(t)

        full_text = "\n".join(combined_text)
        weapon_texts[art["name"]] = full_text
        art["parameters"] = extract_parameters_from_text(art["name"], full_text)

    return weapon_texts


def main():
    print("=" * 60)
    print("步骤2: OCR文本提取 + 图片提取")
    print("=" * 60)

    with open(os.path.join(OUTPUT_DIR, "step1_toc_extract.json"), "r", encoding="utf-8") as f:
        toc_data = json.load(f)

    doc = fitz.open(PDF_PATH)

    print("\n[1/3] OCR提取全部页面文本...")
    cache_path = os.path.join(OUTPUT_DIR, "step2_ocr_cache.json")
    page_texts = {}
    if IMAGES_ONLY:
        print("  IMAGES_ONLY=1，仅重跑图片，不执行OCR。")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                page_texts = {int(k): v for k, v in json.load(f).items()}
    else:
        if os.path.exists(cache_path):
            print("  发现OCR缓存,直接加载")
            with open(cache_path, "r", encoding="utf-8") as f:
                page_texts = json.load(f)
            page_texts = {int(k): v for k, v in page_texts.items()}
        else:
            page_texts = ocr_all_pages(doc)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({str(k): v for k, v in page_texts.items()}, f, ensure_ascii=False)
            print("  OCR完成,已缓存至 step2_ocr_cache.json")

    print("\n[2/3] 提取武器图片并对齐...")
    image_map, image_meta = extract_images_from_pdf(doc, toc_data)
    print(f"  提取图片: {len(image_map)} 张")
    if image_meta:
        preview = list(image_meta.items())[:5]
        for name, meta in preview:
            print(f"    {name} -> {meta['method']} | {meta['size']}")

    print("\n[3/3] 分配文本到武器实体并提取参数...")
    if page_texts:
        weapon_texts = assign_texts_to_weapons(page_texts, toc_data)
    else:
        weapon_texts = {}
        old_step2_path = os.path.join(OUTPUT_DIR, "step2_ocr_extract.json")
        if os.path.exists(old_step2_path):
            with open(old_step2_path, "r", encoding="utf-8") as f:
                old_step2 = json.load(f)
            old_artillery = {art["name"]: art for art in old_step2.get("artillery", [])}
            for art in toc_data["artillery"]:
                art["parameters"] = old_artillery.get(art["name"], {}).get("parameters", {})
        print("  未重新抽取正文，沿用旧参数。")

    param_count = sum(len(art.get("parameters", {})) for art in toc_data["artillery"])
    print(f"  提取参数总数: {param_count}")

    output = {
        "artillery": toc_data["artillery"],
        "countries": toc_data["countries"],
        "categories": toc_data["categories"],
        "relations": toc_data["relations"],
        "image_map": image_map,
        "image_meta": image_meta,
        "weapon_texts": {k: v[:500] for k, v in weapon_texts.items()},
        "image_binding": [
            {
                "name": art["name"],
                "page": art["page"],
                "image_path": image_map.get(art["name"], ""),
                "image_method": image_meta.get(art["name"], {}).get("method", ""),
            }
            for art in toc_data["artillery"]
        ],
    }

    with open(os.path.join(OUTPUT_DIR, "step2_ocr_extract.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    if weapon_texts:
        with open(os.path.join(OUTPUT_DIR, "step2_weapon_full_texts.json"), "w", encoding="utf-8") as f:
            json.dump(weapon_texts, f, ensure_ascii=False, indent=2)

    doc.close()
    print("\n已保存至 data/output/step2_ocr_extract.json 和 step2_weapon_full_texts.json")
    print("图片保存在 data/images/ 目录")
    return output, weapon_texts


if __name__ == "__main__":
    main()
