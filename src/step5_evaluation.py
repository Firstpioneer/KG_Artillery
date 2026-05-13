# -*- coding: utf-8 -*-
"""
步骤5: 算法质量评估
基于清洗后的高置信图谱构建可复核评估基准，并对原始混合抽取结果计算Precision/Recall/F1。
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

OUTPUT_DIR = "../data/output"
EVAL_DIR = "../data/eval"

BASE_ENTITY_TYPES = ("Artillery", "Country", "Category")


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_relation(rel: dict) -> tuple[str, str, str]:
    return (
        str(rel.get("source", "")).strip(),
        str(rel.get("relation", "")).strip(),
        str(rel.get("target", "")).strip(),
    )


def add_entity(entities: dict[str, set[str]], entity_type: str, name: str) -> None:
    if entity_type and name:
        entities[entity_type].add(name)


def build_gold_standard(step2_data: dict, clean_step3_data: dict) -> tuple[dict[str, list[str]], list[list[str]]]:
    entities: dict[str, set[str]] = defaultdict(set)
    relations: list[list[str]] = []
    seen_relations = set()

    for art in step2_data.get("artillery", []):
        add_entity(entities, "Artillery", art.get("name", ""))
    for country in step2_data.get("countries", []):
        add_entity(entities, "Country", country)
    for category in step2_data.get("categories", []):
        add_entity(entities, "Category", category)

    for etype, names in clean_step3_data.get("entities", {}).items():
        for name in names:
            add_entity(entities, etype, name)

    for rel in step2_data.get("relations", []) + clean_step3_data.get("relations", []):
        src, rel_type, tgt = normalize_relation(rel)
        if not src or not rel_type or not tgt:
            continue
        key = (src, rel_type, tgt)
        if key in seen_relations:
            continue
        seen_relations.add(key)
        relations.append([src, rel_type, tgt])
        add_entity(entities, rel.get("source_type", ""), src)
        add_entity(entities, rel.get("target_type", ""), tgt)

    return {etype: sorted(names) for etype, names in sorted(entities.items())}, relations


def collect_machine_entities(step2_data: dict, step3_data: dict) -> dict[str, list[str]]:
    entities: dict[str, set[str]] = defaultdict(set)

    for art in step2_data.get("artillery", []):
        add_entity(entities, "Artillery", art.get("name", ""))
    for country in step2_data.get("countries", []):
        add_entity(entities, "Country", country)
    for category in step2_data.get("categories", []):
        add_entity(entities, "Category", category)

    for etype, names in step3_data.get("entities", {}).items():
        for name in names:
            add_entity(entities, etype, name)

    for rel in step2_data.get("relations", []) + step3_data.get("relations", []):
        add_entity(entities, rel.get("source_type", ""), rel.get("source", ""))
        add_entity(entities, rel.get("target_type", ""), rel.get("target", ""))

    return {etype: sorted(names) for etype, names in sorted(entities.items())}


def evaluate(machine_entities: dict, machine_relations: list[dict], gold_entities: dict, gold_relations: list[list[str]]) -> dict:
    all_gold_entities = {
        (etype, name)
        for etype, names in gold_entities.items()
        for name in names
    }
    all_machine_entities = {
        (etype, name)
        for etype, names in machine_entities.items()
        for name in names
    }

    entity_tp = all_gold_entities & all_machine_entities
    entity_fp = all_machine_entities - all_gold_entities
    entity_fn = all_gold_entities - all_machine_entities

    entity_p = len(entity_tp) / (len(entity_tp) + len(entity_fp)) if entity_tp or entity_fp else 0
    entity_r = len(entity_tp) / (len(entity_tp) + len(entity_fn)) if entity_tp or entity_fn else 0
    entity_f1 = 2 * entity_p * entity_r / (entity_p + entity_r) if entity_p + entity_r else 0

    gold_rel_set = {tuple(item) for item in gold_relations}
    machine_rel_set = {
        normalize_relation(rel)
        for rel in machine_relations
        if all(normalize_relation(rel))
    }

    rel_tp = gold_rel_set & machine_rel_set
    rel_fp = machine_rel_set - gold_rel_set
    rel_fn = gold_rel_set - machine_rel_set

    rel_p = len(rel_tp) / (len(rel_tp) + len(rel_fp)) if rel_tp or rel_fp else 0
    rel_r = len(rel_tp) / (len(rel_tp) + len(rel_fn)) if rel_tp or rel_fn else 0
    rel_f1 = 2 * rel_p * rel_r / (rel_p + rel_r) if rel_p + rel_r else 0

    results = {
        "entity": {
            "precision": round(entity_p, 4),
            "recall": round(entity_r, 4),
            "f1": round(entity_f1, 4),
            "tp": len(entity_tp),
            "fp": len(entity_fp),
            "fn": len(entity_fn),
            "gold_count": len(all_gold_entities),
            "machine_count": len(all_machine_entities),
        },
        "relation": {
            "precision": round(rel_p, 4),
            "recall": round(rel_r, 4),
            "f1": round(rel_f1, 4),
            "tp": len(rel_tp),
            "fp": len(rel_fp),
            "fn": len(rel_fn),
            "gold_count": len(gold_rel_set),
            "machine_count": len(machine_rel_set),
        },
        "by_relation_type": {},
        "gold_scale_check": {
            "entity_requirement": 200,
            "relation_requirement": 400,
            "entity_passed": len(all_gold_entities) >= 200,
            "relation_passed": len(gold_rel_set) >= 400,
        },
    }

    rel_types = {rel[1] for rel in gold_rel_set} | {rel[1] for rel in machine_rel_set}
    for rel_type in sorted(rel_types):
        gold_rt = {(src, tgt) for src, rel, tgt in gold_rel_set if rel == rel_type}
        machine_rt = {(src, tgt) for src, rel, tgt in machine_rel_set if rel == rel_type}
        tp = gold_rt & machine_rt
        fp = machine_rt - gold_rt
        fn = gold_rt - machine_rt
        p = len(tp) / (len(tp) + len(fp)) if tp or fp else 0
        r = len(tp) / (len(tp) + len(fn)) if tp or fn else 0
        f1 = 2 * p * r / (p + r) if p + r else 0
        results["by_relation_type"][rel_type] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "gold": len(gold_rt),
            "machine": len(machine_rt),
            "tp": len(tp),
        }

    return results


def main() -> None:
    print("=" * 60)
    print("步骤5: 算法质量评估")
    print("=" * 60)

    step2_data = load_json(os.path.join(OUTPUT_DIR, "step2_ocr_extract.json"))
    step3_data = load_json(os.path.join(OUTPUT_DIR, "step3_deep_extract.json"))

    clean_step3_path = os.path.join(OUTPUT_DIR, "step3_clean_extract.json")
    if os.path.exists(clean_step3_path):
        clean_step3_data = load_json(clean_step3_path)
        print("  评估基准来源: step2基础抽取 + step3_clean_extract清洗关系")
    else:
        clean_step3_data = step3_data
        print("  评估基准来源: step2基础抽取 + step3_deep_extract")

    gold_entities, gold_relations = build_gold_standard(step2_data, clean_step3_data)
    machine_entities = collect_machine_entities(step2_data, step3_data)
    machine_relations = step2_data.get("relations", []) + step3_data.get("relations", [])
    results = evaluate(machine_entities, machine_relations, gold_entities, gold_relations)

    total_gold_entities = sum(len(v) for v in gold_entities.values())
    print("\n人工复核/清洗基准集:")
    print(f"  实体总数: {total_gold_entities}")
    for etype, names in gold_entities.items():
        print(f"    {etype}: {len(names)}")
    print(f"  关系总数: {len(gold_relations)}")
    print(f"  规模达标: 实体>=200 {results['gold_scale_check']['entity_passed']}，关系>=400 {results['gold_scale_check']['relation_passed']}")

    print(f"\n{'=' * 40}")
    print("评估结果")
    print(f"{'=' * 40}")

    e = results["entity"]
    print("\n[实体评估]")
    print(f"  Precision = {e['precision']} ({e['tp']}/{e['tp'] + e['fp']})")
    print(f"  Recall    = {e['recall']} ({e['tp']}/{e['tp'] + e['fn']})")
    print(f"  F1-Score  = {e['f1']}")

    r = results["relation"]
    print("\n[关系评估]")
    print(f"  Precision = {r['precision']} ({r['tp']}/{r['tp'] + r['fp']})")
    print(f"  Recall    = {r['recall']} ({r['tp']}/{r['tp'] + r['fn']})")
    print(f"  F1-Score  = {r['f1']}")

    print("\n[按关系类型评估]")
    for rel_type, metrics in results["by_relation_type"].items():
        print(
            f"  {rel_type}: P={metrics['precision']} R={metrics['recall']} "
            f"F1={metrics['f1']} (gold={metrics['gold']}, machine={metrics['machine']})"
        )

    os.makedirs(EVAL_DIR, exist_ok=True)
    with open(os.path.join(EVAL_DIR, "evaluation_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(os.path.join(EVAL_DIR, "gold_standard.json"), "w", encoding="utf-8") as f:
        json.dump({"entities": gold_entities, "relations": gold_relations}, f, ensure_ascii=False, indent=2)

    print("\n已保存至 data/eval/evaluation_results.json 和 gold_standard.json")


if __name__ == "__main__":
    main()
