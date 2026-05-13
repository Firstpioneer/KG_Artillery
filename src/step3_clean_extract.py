# -*- coding: utf-8 -*-
"""
步骤3.5: 清洗深度抽取结果
目标:
1. 过滤明显错误的Derivative/War/Chassis/Equipped关系
2. 生成更适合应用展示和Neo4j导入的清洗版图谱
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

OUTPUT_DIR = "../data/output"

KEEP_RELATIONS = {
    "DEVELOPED_IN",
    "IS_TYPE_OF",
    "DESIGNED_BY",
    "USES_AMMO",
    "DERIVED_FROM",
    "PARTICIPATED_IN",
    "USES_CHASSIS",
    "EQUIPPED_BY",
}

VALID_WARS = {
    "一战", "二战", "海湾战争", "朝鲜战争", "越南战争", "阿富汗战争", "伊拉克战争",
    "冷战", "中东战争", "两伊战争", "太平洋战争", "苏德战争", "马岛战争",
    "诺曼底登陆", "纳卡冲突",
}


def looks_like_valid_derivative(name: str) -> bool:
    if not name or len(name) > 24:
        return False
    if any(token in name for token in ["换装", "安装", "整合", "由", "最初称", "炮塔", "瞄准具", "衍生型", "火炮"]):
        return False
    if re.fullmatch(r"\d{4,}", name):
        return False
    if len(re.findall(r"[一-龥]", name)) > 6:
        return False
    return bool(re.search(r"[A-Za-z0-9]", name))


def looks_like_valid_chassis(name: str) -> bool:
    bad_tokens = ["谢尔曼坦克", "坦克", "步兵战车", "装甲车"]
    if not name:
        return False
    if "底盘" in name or "卡车" in name:
        return True
    return not any(token == name for token in bad_tokens)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    step2 = load_json(os.path.join(OUTPUT_DIR, "step2_ocr_extract.json"))
    step3 = load_json(os.path.join(OUTPUT_DIR, "step3_deep_extract.json"))

    artillery_names = {art["name"] for art in step2["artillery"]}
    artillery_country = {art["name"]: art["countries"][0] for art in step2["artillery"] if art.get("countries")}

    cleaned_entities = defaultdict(set)
    cleaned_relations = []
    seen = set()

    # 先保留step2基础关系
    for rel in step2.get("relations", []):
        key = (rel["source"], rel["relation"], rel["target"])
        if key not in seen:
            cleaned_relations.append(rel)
            seen.add(key)

    # 清洗step3关系
    for rel in step3.get("relations", []):
        relation = rel.get("relation", "")
        source = rel.get("source", "")
        target = rel.get("target", "")
        source_type = rel.get("source_type", "")
        target_type = rel.get("target_type", "")

        if relation not in KEEP_RELATIONS or not source or not target:
            continue

        if relation == "DERIVED_FROM":
            if target not in artillery_names:
                continue
            if not looks_like_valid_derivative(source):
                continue
            if source in target:
                continue

        if relation == "PARTICIPATED_IN":
            if target not in VALID_WARS:
                continue

        if relation == "USES_CHASSIS":
            if not looks_like_valid_chassis(target):
                continue

        if relation == "EQUIPPED_BY":
            home_country = artillery_country.get(source)
            if home_country and target == home_country:
                continue

        key = (source, relation, target)
        if key in seen:
            continue
        seen.add(key)
        cleaned_relations.append(rel)

        if source_type and source_type != "Artillery":
            cleaned_entities[source_type].add(source)
        if target_type and target_type not in {"Artillery", "Category", "Country"}:
            cleaned_entities[target_type].add(target)
        if target_type == "Country":
            cleaned_entities["Country"].add(target)

    # 补基础实体
    for art in step2["artillery"]:
        pass

    out = {
        "entities": {k: sorted(v) for k, v in cleaned_entities.items()},
        "relations": cleaned_relations,
    }

    out_path = os.path.join(OUTPUT_DIR, "step3_clean_extract.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    rel_counter = Counter(rel["relation"] for rel in cleaned_relations)
    print("已生成清洗版关系文件:", out_path)
    print("关系统计:")
    for name, count in rel_counter.most_common():
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()
