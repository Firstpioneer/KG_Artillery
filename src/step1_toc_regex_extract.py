# -*- coding: utf-8 -*-
"""
步骤1: 基于PDF目录的正则表达式抽取
目标: 提取 Artillery, Country, Category 实体及 DEVELOPED_IN, IS_TYPE_OF, EQUIPPED_BY 关系
优势: 100%准确率，构建基础网络
"""
import fitz
import re
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

PDF_PATH = "../book/全球火炮鉴赏指南（珍藏版） -- 《深度军事》 编委会 -- 世界军事鉴赏指南系列, 2018 -- 清华大学出版社.pdf"

CHAPTER_CATEGORY_MAP = {
    "Chapter 02": "榴弹炮",
    "Chapter 03": "迫击炮",
    "Chapter 04": "火箭炮",
    "Chapter 05": "反坦克炮",
    "Chapter 06": "防空火炮",
    "Chapter 07": "舰炮",
}

# 有序国家列表(长的优先匹配)
COUNTRY_PATTERNS = [
    ("英国/德国/意大利", ["英国", "德国", "意大利"]),
    ("捷克斯洛伐克", ["捷克斯洛伐克"]),
    ("俄罗斯", ["俄罗斯"]),
    ("苏联", ["苏联"]),
    ("德国", ["德国"]),
    ("美国", ["美国"]),
    ("英国", ["英国"]),
    ("法国", ["法国"]),
    ("瑞典", ["瑞典"]),
    ("日本", ["日本"]),
    ("韩国", ["韩国"]),
    ("波兰", ["波兰"]),
    ("巴西", ["巴西"]),
    ("印度", ["印度"]),
    ("瑞士", ["瑞士"]),
    ("意大利", ["意大利"]),
]

MODIFIERS = ["自行", "多管", "轮式", "遥控", "多口径", "型"]

TYPE_SUFFIXES = r'(榴弹炮|迫击炮|火箭炮|反坦克炮|高射炮|防空炮|防空系统|舰炮|加农炮|榴弹发射器)'


def match_country(raw_str):
    for pattern, countries in COUNTRY_PATTERNS:
        if raw_str.startswith(pattern):
            return countries, raw_str[len(pattern):]
    return None, raw_str


def detect_subtype(model_str):
    for kw in MODIFIERS:
        if kw in model_str:
            return kw
    return ""


def extract_from_toc():
    doc = fitz.open(PDF_PATH)
    toc = doc.get_toc()

    artillery_list = []
    country_set = set()
    category_set = set()
    relations = []
    current_chapter = None
    current_category = None

    for level, title, page_num in toc:
        if level == 1:
            for ch_key, ch_cat in CHAPTER_CATEGORY_MAP.items():
                if ch_key in title:
                    current_chapter = ch_key
                    current_category = ch_cat
                    category_set.add(ch_cat)
                    break
            continue

        if level != 2 or not current_chapter:
            continue

        clean_title = title.replace('“', '').replace('”', '').replace('„', '').replace('‟', '').strip()

        countries, remainder = match_country(clean_title)
        if not countries:
            print(f"[WARN] 无法匹配国家: {title}")
            continue

        # 有口径
        pattern_with_caliber = r'^(\d+)毫米(.+?)' + TYPE_SUFFIXES + r'$'
        m = re.match(pattern_with_caliber, remainder)
        if m:
            caliber = m.group(1) + "毫米"
            model_raw = m.group(2).strip()
            weapon_type = m.group(3)
        else:
            # 无口径
            pattern_no_caliber = r'^(.+?)' + TYPE_SUFFIXES + r'$'
            m2 = re.match(pattern_no_caliber, remainder)
            if m2:
                caliber = ""
                model_raw = m2.group(1).strip()
                weapon_type = m2.group(2)
            else:
                print(f"[WARN] 无法解析: {title} (remainder={remainder})")
                continue

        subtype = detect_subtype(model_raw)
        core_model = model_raw
        for mod in MODIFIERS:
            core_model = core_model.replace(mod, "")
        core_model = core_model.strip()

        full_name = clean_title

        artillery = {
            "name": full_name,
            "model": model_raw,
            "core_model": core_model,
            "caliber": caliber,
            "category": current_category,
            "subtype": subtype,
            "page": page_num,
            "countries": countries,
        }
        artillery_list.append(artillery)

        for c in countries:
            country_set.add(c)

        # DEVELOPED_IN: 第一个国家
        relations.append({
            "source": full_name,
            "source_type": "Artillery",
            "relation": "DEVELOPED_IN",
            "target": countries[0],
            "target_type": "Country",
        })
        # 多国联合时其他国家为 EQUIPPED_BY
        for c in countries[1:]:
            relations.append({
                "source": full_name,
                "source_type": "Artillery",
                "relation": "EQUIPPED_BY",
                "target": c,
                "target_type": "Country",
            })

        # IS_TYPE_OF
        relations.append({
            "source": full_name,
            "source_type": "Artillery",
            "relation": "IS_TYPE_OF",
            "target": current_category,
            "target_type": "Category",
        })

    doc.close()
    return artillery_list, sorted(country_set), sorted(category_set), relations


def main():
    print("=" * 60)
    print("步骤1: 基于目录正则抽取")
    print("=" * 60)

    artillery_list, country_list, category_list, relations = extract_from_toc()

    print(f"\n抽取结果统计:")
    print(f"  Artillery (火炮): {len(artillery_list)}")
    print(f"  Country (国家): {len(country_list)}")
    print(f"  Category (类别): {len(category_list)}")
    print(f"  关系总数: {len(relations)}")
    rel_counts = {}
    for r in relations:
        rel_counts[r['relation']] = rel_counts.get(r['relation'], 0) + 1
    for k, v in sorted(rel_counts.items()):
        print(f"    {k}: {v}")

    print(f"\n国家列表: {country_list}")
    print(f"类别列表: {category_list}")
    print(f"\n前10条武器:")
    for a in artillery_list[:10]:
        print(f"  {a['name']} | 口径={a['caliber']} | 型号={a['model']} | 核心={a['core_model']} | 子类={a['subtype']}")

    output = {
        "artillery": artillery_list,
        "countries": country_list,
        "categories": category_list,
        "relations": relations,
    }

    with open("../data/output/step1_toc_extract.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n已保存至 data/output/step1_toc_extract.json")
    return output


if __name__ == "__main__":
    main()
