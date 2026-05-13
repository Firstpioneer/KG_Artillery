from __future__ import annotations

import json
import math
import os
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "data" / "output"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

VISIBLE_RELATIONS = {
    "DEVELOPED_IN",
    "IS_TYPE_OF",
    "DESIGNED_BY",
    "USES_AMMO",
    "DERIVED_FROM",
    "PARTICIPATED_IN",
    "USES_CHASSIS",
    "EQUIPPED_BY",
}

VISIBLE_LABELS = {
    "Artillery",
    "Country",
    "Category",
    "Institution",
    "Designer",
    "Ammunition",
    "Derivative",
    "War",
    "Chassis",
}

RELATION_LABEL = {
    "DEVELOPED_IN": "研发国家",
    "IS_TYPE_OF": "类型",
    "DESIGNED_BY": "设计方",
    "USES_AMMO": "弹药",
    "DERIVED_FROM": "衍生型号",
    "PARTICIPATED_IN": "参战",
    "USES_CHASSIS": "底盘",
    "EQUIPPED_BY": "装备国家",
}


@dataclass
class GraphBundle:
    nodes: List[dict]
    edges: List[dict]
    node_index: Dict[str, dict]
    outgoing: Dict[str, List[dict]]
    incoming: Dict[str, List[dict]]
    artillery_names: List[str]
    label_names: Dict[str, List[str]]
    raw_step2: dict
    raw_step3: dict


def _safe_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").replace("米", "").replace("千米", "000").strip())
    except (TypeError, ValueError):
        return None


def _canonical_path(path_str: str) -> str:
    if not path_str:
        return ""
    path = Path(path_str)
    if not path.is_absolute():
        if str(path).startswith("..\\data") or str(path).startswith("../data"):
            path = (ROOT_DIR / "src" / path).resolve()
        else:
            path = (ROOT_DIR / path).resolve()
    return str(path)


def _normalize_name(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _looks_like_valid_derivative(name: str) -> bool:
    if not name or len(name) > 24:
        return False
    if any(token in name for token in ["换装", "安装", "整合", "由", "最初称", "炮塔", "瞄准具", "火炮", "系统衍生型"]):
        return False
    if re.fullmatch(r"\d{4,}", name):
        return False
    if " " in name and len(name) > 16:
        return False
    if len(re.findall(r"[一-龥]", name)) > 6:
        return False
    return bool(re.search(r"[A-Za-z0-9]", name))


def _node_allowed(label: str, name: str, view: str = "trusted") -> bool:
    if not name:
        return False
    if view == "full":
        return True
    if label not in VISIBLE_LABELS:
        return False
    if label == "Derivative":
        return _looks_like_valid_derivative(name)
    return True


def _edge_allowed(rel: dict, view: str = "trusted") -> bool:
    relation = rel.get("relation", "")
    if relation not in VISIBLE_RELATIONS and view != "full":
        return False
    source = rel.get("source", "")
    target = rel.get("target", "")
    source_type = rel.get("source_type", "")
    target_type = rel.get("target_type", "")
    if not source or not target:
        return False
    if not _node_allowed(source_type, source, view=view):
        return False
    if not _node_allowed(target_type, target, view=view):
        return False
    if relation == "EQUIPPED_BY" and source == target:
        return False
    if relation == "DERIVED_FROM" and source in target:
        return False
    return True


def load_graph_bundle(view: str = "trusted") -> GraphBundle:
    step2 = json.loads((OUTPUT_DIR / "step2_ocr_extract.json").read_text(encoding="utf-8"))
    clean_step3_path = OUTPUT_DIR / "step3_clean_extract.json"
    if view == "full":
        step3_path = OUTPUT_DIR / "step3_deep_extract.json"
    else:
        step3_path = clean_step3_path if clean_step3_path.exists() else OUTPUT_DIR / "step3_deep_extract.json"
    step3 = json.loads(step3_path.read_text(encoding="utf-8"))

    nodes: List[dict] = []
    node_index: Dict[str, dict] = {}
    label_names: Dict[str, List[str]] = defaultdict(list)

    def add_node(name: str, label: str, **props: object) -> None:
        if not name or not _node_allowed(label, name, view=view):
            return
        node = node_index.get(name)
        if node is None:
            node = {"id": name, "name": name, "label": label}
            node_index[name] = node
            nodes.append(node)
            label_names[label].append(name)
        node.update({k: v for k, v in props.items() if v not in (None, "")})

    for artillery in step2["artillery"]:
        params = artillery.get("parameters", {})
        add_node(
            artillery["name"],
            "Artillery",
            category=artillery.get("category", ""),
            caliber=artillery.get("caliber", ""),
            model=artillery.get("model", ""),
            core_model=artillery.get("core_model", ""),
            subtype=artillery.get("subtype", ""),
            page=artillery.get("page", 0),
            image_path=_canonical_path(step2.get("image_map", {}).get(artillery["name"], "")),
            weight=params.get("weight", ""),
            range=params.get("range", ""),
            rate_of_fire=params.get("rate_of_fire", ""),
            length=params.get("length", ""),
            barrel_length=params.get("barrel_length", ""),
            width=params.get("width", ""),
            height=params.get("height", ""),
        )

    for name in step2.get("countries", []):
        add_node(name, "Country")
    for name in step2.get("categories", []):
        add_node(name, "Category")
    for label, names in step3.get("entities", {}).items():
        for name in names:
            add_node(name, label)

    edges: List[dict] = []
    outgoing: Dict[str, List[dict]] = defaultdict(list)
    incoming: Dict[str, List[dict]] = defaultdict(list)
    edge_seen = set()

    def add_edge(rel: dict) -> None:
        source = rel.get("source", "")
        relation = rel.get("relation", "")
        target = rel.get("target", "")
        source_type = rel.get("source_type", "")
        target_type = rel.get("target_type", "")
        if not _edge_allowed(rel, view=view):
            return
        if source not in node_index:
            add_node(source, source_type or "Unknown")
        if target not in node_index:
            add_node(target, target_type or "Unknown")
        if source not in node_index or target not in node_index:
            return
        key = (source, relation, target)
        if key in edge_seen:
            return
        edge_seen.add(key)
        edge = {
            "source": source,
            "target": target,
            "relation": relation,
            "relation_label": RELATION_LABEL.get(relation, relation),
            "source_type": source_type or node_index[source]["label"],
            "target_type": target_type or node_index[target]["label"],
            "method": rel.get("method", "base"),
            "description": rel.get("description", ""),
        }
        edges.append(edge)
        outgoing[source].append(edge)
        incoming[target].append(edge)

    for rel in step2.get("relations", []):
        add_edge(rel)
    for rel in step3.get("relations", []):
        add_edge(rel)

    return GraphBundle(
        nodes=nodes,
        edges=edges,
        node_index=node_index,
        outgoing=outgoing,
        incoming=incoming,
        artillery_names=sorted(label_names.get("Artillery", [])),
        label_names={k: sorted(v) for k, v in label_names.items()},
        raw_step2=step2,
        raw_step3=step3,
    )


def graph_stats(bundle: GraphBundle) -> dict:
    label_counter = Counter(node["label"] for node in bundle.nodes)
    rel_counter = Counter(edge["relation"] for edge in bundle.edges)
    country_counter = Counter()
    category_counter = Counter()
    war_counter = Counter()
    institution_counter = Counter()

    for art_name in bundle.artillery_names:
        artillery = bundle.node_index.get(art_name, {})
        if artillery.get("category"):
            category_counter[artillery["category"]] += 1
        for edge in bundle.outgoing.get(art_name, []):
            if edge["relation"] == "DEVELOPED_IN":
                country_counter[edge["target"]] += 1
            elif edge["relation"] == "PARTICIPATED_IN":
                war_counter[edge["target"]] += 1
            elif edge["relation"] == "DESIGNED_BY":
                institution_counter[edge["target"]] += 1

    return {
        "node_total": len(bundle.nodes),
        "edge_total": len(bundle.edges),
        "top_labels": label_counter.most_common(),
        "top_relations": rel_counter.most_common(),
        "top_countries": country_counter.most_common(12),
        "top_categories": category_counter.most_common(12),
        "top_wars": war_counter.most_common(12),
        "top_institutions": institution_counter.most_common(12),
    }


def fuzzy_find_name(bundle: GraphBundle, query: str, label: Optional[str] = None) -> Optional[str]:
    if not query:
        return None
    candidates = bundle.label_names.get(label, []) if label else list(bundle.node_index.keys())
    if query in candidates:
        return query
    normalized = _normalize_name(query)
    for name in candidates:
        if normalized == _normalize_name(name):
            return name
    for name in candidates:
        if normalized in _normalize_name(name):
            return name
    return None


def _find_label_match(bundle: GraphBundle, label: str, question: str) -> Optional[str]:
    normalized_question = _normalize_name(question)
    for name in bundle.label_names.get(label, []):
        normalized_name = _normalize_name(name)
        if normalized_name and normalized_name in normalized_question:
            return name
    return None


def load_weapon_texts() -> dict:
    path = OUTPUT_DIR / "step2_weapon_full_texts.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _tokenize_query(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]*|[一-龥]{2,}", text)
    stop_words = {"什么", "哪些", "哪个", "如何", "介绍", "一下", "这个", "火炮", "武器", "装备", "性能", "特点", "关系", "知识", "图谱"}
    return [token for token in tokens if token not in stop_words]


def retrieve_qa_context(bundle: GraphBundle, question: str, top_k: int = 4) -> dict:
    normalized_question = _normalize_name(question)
    tokens = _tokenize_query(question)
    weapon_texts = load_weapon_texts()
    candidates = []

    for art_name in bundle.artillery_names:
        node = bundle.node_index.get(art_name, {})
        text = weapon_texts.get(art_name, "")
        searchable = _normalize_name(" ".join([
            art_name,
            node.get("model", ""),
            node.get("core_model", ""),
            node.get("category", ""),
            text[:1800],
        ]))
        score = 0
        if _normalize_name(art_name) in normalized_question:
            score += 12
        if node.get("model") and _normalize_name(str(node["model"])) in normalized_question:
            score += 8
        for token in tokens:
            normalized_token = _normalize_name(token)
            if normalized_token and normalized_token in searchable:
                score += 2 if len(token) > 2 else 1
        for edge in bundle.outgoing.get(art_name, []):
            if _normalize_name(edge["target"]) in normalized_question:
                score += 5
        if score > 0:
            candidates.append((score, art_name, node, text))

    matched_nodes = []
    for label, names in bundle.label_names.items():
        for name in names:
            if _normalize_name(name) in normalized_question:
                matched_nodes.append((label, name))

    if not candidates and matched_nodes:
        related = set()
        for _, name in matched_nodes:
            for edge in bundle.incoming.get(name, []):
                if edge.get("source_type") == "Artillery":
                    related.add(edge["source"])
            for edge in bundle.outgoing.get(name, []):
                if edge.get("target_type") == "Artillery":
                    related.add(edge["target"])
        for art_name in sorted(related)[:top_k]:
            candidates.append((3, art_name, bundle.node_index.get(art_name, {}), weapon_texts.get(art_name, "")))

    candidates = sorted(candidates, key=lambda item: item[0], reverse=True)[:top_k]
    context_blocks = []
    for score, art_name, node, text in candidates:
        facts = []
        for key, label in [("category", "类别"), ("caliber", "口径"), ("range", "射程"), ("weight", "重量"), ("rate_of_fire", "射速")]:
            if node.get(key):
                facts.append(f"{label}: {node[key]}")
        rels = [f"{edge['relation_label']}->{edge['target']}" for edge in bundle.outgoing.get(art_name, [])[:12]]
        context_blocks.append(
            "\n".join([
                f"【火炮】{art_name}",
                f"基础属性：{'；'.join(facts) if facts else '无'}",
                f"图谱关系：{'；'.join(rels) if rels else '无'}",
                f"原书OCR摘录：{text[:1200] if text else '无'}",
            ])
        )

    relevance_score = sum(item[0] for item in candidates) + len(matched_nodes) * 2
    return {
        "is_relevant": relevance_score >= 3,
        "score": relevance_score,
        "matched_nodes": matched_nodes[:8],
        "contexts": context_blocks,
        "sources": [item[1] for item in candidates],
    }


def _call_deepseek(prompt: str, api_key: str) -> str:
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是《全球火炮鉴赏指南》知识图谱科普网站的问答助手。只能基于给定知识库上下文回答；如果上下文不足，明确说无法从知识库确认。回答要准确、自然、有条理，不要编造。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 900,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return f"DeepSeek 调用失败：{exc}"


def answer_question_with_rag(bundle: GraphBundle, question: str, api_key: str | None = None) -> dict:
    q = question.strip()
    if not q:
        return {"answer": "请输入问题。", "sources": [], "used_deepseek": False, "is_relevant": False}

    retrieval = retrieve_qa_context(bundle, q)
    if not retrieval["is_relevant"]:
        return {
            "answer": "这个问题与当前《全球火炮鉴赏指南》知识库没有明显关联，我只能回答本书和已构建火炮知识图谱范围内的问题。",
            "sources": [],
            "used_deepseek": False,
            "is_relevant": False,
        }

    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key:
        prompt = f"""用户问题：{q}

知识库上下文：
{chr(10).join(retrieval['contexts'])}

请根据上下文回答。要求：
1. 如果上下文能回答，给出自然、有解释性的中文回答。
2. 涉及具体火炮时列出关键依据，如口径、射程、国家、战争或关系。
3. 不要使用上下文外知识；无法确认时说明“知识库中没有足够证据”。
4. 如果问题偏离火炮知识库，拒绝回答。"""
        answer = _call_deepseek(prompt, api_key)
        return {"answer": answer, "sources": retrieval["sources"], "used_deepseek": True, "is_relevant": True}

    fallback = answer_question(bundle, q)
    if fallback.startswith("暂不支持"):
        fallback = "已找到相关知识库内容，但尚未配置 DeepSeek API Key，因此只能给出检索摘要：\n" + "\n\n".join(retrieval["contexts"][:2])
    return {"answer": fallback, "sources": retrieval["sources"], "used_deepseek": False, "is_relevant": True}


def one_hop_subgraph(bundle: GraphBundle, center_name: str, max_nodes: int = 14) -> dict:
    center = bundle.node_index.get(center_name)
    if center is None:
        return {"nodes": [], "edges": []}

    candidate_edges = []
    candidate_edges.extend(bundle.outgoing.get(center_name, []))
    candidate_edges.extend(bundle.incoming.get(center_name, []))

    priority = {
        "DEVELOPED_IN": 1,
        "IS_TYPE_OF": 2,
        "DESIGNED_BY": 3,
        "USES_CHASSIS": 4,
        "USES_AMMO": 5,
        "PARTICIPATED_IN": 6,
        "EQUIPPED_BY": 7,
        "DERIVED_FROM": 8,
    }
    candidate_edges = sorted(
        candidate_edges,
        key=lambda edge: (priority.get(edge["relation"], 99), edge["target"], edge["source"]),
    )

    node_ids = {center_name}
    edges = []
    for edge in candidate_edges:
        other = edge["target"] if edge["source"] == center_name else edge["source"]
        if len(node_ids) >= max_nodes and other not in node_ids:
            continue
        node_ids.add(other)
        edges.append(edge)

    nodes = [bundle.node_index[node_id] for node_id in node_ids]
    return {"nodes": nodes, "edges": edges}


def global_subgraph(bundle: GraphBundle) -> dict:
    return {"nodes": bundle.nodes, "edges": bundle.edges}


def relationship_groups(bundle: GraphBundle, artillery_name: str) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = defaultdict(list)
    for edge in bundle.outgoing.get(artillery_name, []):
        groups[edge["relation_label"]].append(edge["target"])
    for edge in bundle.incoming.get(artillery_name, []):
        if edge["relation"] == "DERIVED_FROM":
            groups["衍生型号"].append(edge["source"])
    return {k: sorted(dict.fromkeys(v)) for k, v in groups.items()}


def parameter_profile(artillery: dict) -> List[dict]:
    metrics = [
        ("caliber", "口径", _safe_float(str(artillery.get("caliber", "")).replace("毫米", "")), "mm", 240),
        ("range", "射程", _safe_float(artillery.get("range")), "m", 45000),
        ("weight", "重量", _safe_float(artillery.get("weight")), "kg", 50000),
        ("rate_of_fire", "射速", _safe_float(artillery.get("rate_of_fire")), "发/分", 30),
        ("length", "全长", _safe_float(artillery.get("length")), "m", 15),
        ("height", "全高", _safe_float(artillery.get("height")), "m", 5),
    ]
    profile = []
    for key, name, value, unit, max_value in metrics:
        if value is None:
            continue
        score = min(max(value / max_value * 100, 0), 100)
        display_value = int(value) if float(value).is_integer() else round(value, 2)
        profile.append({
            "key": key,
            "metric": name,
            "value": value,
            "display_value": display_value,
            "unit": unit,
            "score": round(score, 1),
            "max_value": max_value,
        })
    return profile


def build_plot_positions(nodes: Iterable[dict], center_name: str | None = None) -> Dict[str, tuple]:
    nodes = list(nodes)
    positions = {}
    if center_name:
        positions[center_name] = (0.0, 0.0)
    label_groups: Dict[str, List[dict]] = defaultdict(list)
    for node in nodes:
        if center_name and node["id"] == center_name:
            continue
        label_groups[node["label"]].append(node)

    ring_order = ["Country", "Category", "Institution", "Designer", "Chassis", "Ammunition", "War", "Derivative", "Artillery"]
    extra_labels = [label for label in sorted(label_groups) if label not in ring_order]
    ordered_labels = ring_order + extra_labels
    if center_name:
        ring_step = 1.2
        ring_index = 1
        for label in ordered_labels:
            group = label_groups.get(label, [])
            if not group:
                continue
            radius = ring_index * ring_step
            total = len(group)
            for idx, node in enumerate(group):
                angle = (2 * math.pi * idx) / max(total, 1)
                positions[node["id"]] = (math.cos(angle) * radius, math.sin(angle) * radius)
            ring_index += 1
        return positions

    label_radius = {
        "Artillery": 6.2,
        "Derivative": 8.2,
        "Country": 1.2,
        "Category": 2.1,
        "Institution": 3.0,
        "Designer": 3.6,
        "Chassis": 4.2,
        "Ammunition": 5.0,
        "War": 5.7,
    }
    label_phase = {label: idx * 0.37 for idx, label in enumerate(ordered_labels)}
    extra_radius_start = max(label_radius.values()) + 1.1
    for extra_index, label in enumerate(extra_labels):
        label_radius[label] = extra_radius_start + extra_index * 0.9
    for label in ordered_labels:
        group = label_groups.get(label, [])
        if not group:
            continue
        radius = label_radius.get(label, 6.8)
        total = len(group)
        for idx, node in enumerate(group):
            angle = (2 * math.pi * idx) / max(total, 1) + label_phase.get(label, 0)
            jitter = 0.18 * ((idx % 5) - 2)
            positions[node["id"]] = (
                math.cos(angle) * (radius + jitter),
                math.sin(angle) * (radius + jitter),
            )
    return positions


def node_brief(artillery: dict) -> List[tuple]:
    return [
        ("类别", artillery.get("category", "未知")),
        ("口径", artillery.get("caliber", "未知")),
        ("型号", artillery.get("model", "未知")),
        ("页码", artillery.get("page", "未知")),
        ("射程", f"{artillery.get('range', '未知')} 米" if artillery.get("range") else "未知"),
        ("重量", f"{artillery.get('weight', '未知')} 千克" if artillery.get("weight") else "未知"),
    ]


def answer_question(bundle: GraphBundle, question: str) -> str:
    q = question.strip()
    if not q:
        return "请输入问题。"

    war = _find_label_match(bundle, "War", q)
    institution = _find_label_match(bundle, "Institution", q)
    chassis = _find_label_match(bundle, "Chassis", q)
    country = _find_label_match(bundle, "Country", q)

    if war and institution and ("哪些" in q or "哪" in q):
        matched = []
        for art_name in bundle.artillery_names:
            rels = bundle.outgoing.get(art_name, [])
            has_war = any(r["relation"] == "PARTICIPATED_IN" and r["target"] == war for r in rels)
            has_inst = any(r["relation"] == "DESIGNED_BY" and r["target"] == institution for r in rels)
            if has_war and has_inst:
                matched.append(art_name)
        if matched:
            return f"{war}中由{institution}设计或生产关联的火炮有: " + "；".join(matched[:12])
        return f"当前清洗后的图谱中未检索到同时满足“{war}”和“{institution}”条件的火炮。"

    if chassis and ("口径最大" in q or "最大口径" in q):
        candidates = []
        for art_name in bundle.artillery_names:
            rels = bundle.outgoing.get(art_name, [])
            if any(r["relation"] == "USES_CHASSIS" and r["target"] == chassis for r in rels):
                caliber = _safe_float(str(bundle.node_index[art_name].get("caliber", "")).replace("毫米", ""))
                if caliber is not None:
                    candidates.append((caliber, art_name))
        if candidates:
            caliber, art_name = max(candidates, key=lambda item: item[0])
            value = int(caliber) if caliber.is_integer() else caliber
            return f"基于{chassis}的火炮中，口径最大的是 {art_name}，口径约为 {value} 毫米。"
        return f"当前清洗后的图谱中未检索到与 {chassis} 相连且带口径属性的火炮。"

    if war and ("哪些火炮" in q or "哪些" in q):
        matched = [
            art_name
            for art_name in bundle.artillery_names
            if any(r["relation"] == "PARTICIPATED_IN" and r["target"] == war for r in bundle.outgoing.get(art_name, []))
        ]
        if matched:
            return f"{war}关联火炮包括: " + "；".join(matched[:15])
        return f"当前图谱中没有检索到 {war} 的关联火炮。"

    if country and ("研制" in q or "研发" in q or "developed" in q.lower()):
        matched = [
            art_name
            for art_name in bundle.artillery_names
            if any(r["relation"] == "DEVELOPED_IN" and r["target"] == country for r in bundle.outgoing.get(art_name, []))
        ]
        if matched:
            return f"{country}研制的火炮示例: " + "；".join(matched[:15])
        return f"当前图谱中没有检索到 {country} 研制火炮。"

    node_name = fuzzy_find_name(bundle, q)
    if node_name:
        outgoing = bundle.outgoing.get(node_name, [])
        incoming = bundle.incoming.get(node_name, [])
        summary = []
        if outgoing:
            sample = "；".join(f"{edge['relation_label']} -> {edge['target']}" for edge in outgoing[:6])
            summary.append(f"出边: {sample}")
        if incoming:
            sample = "；".join(f"{edge['source']} -> {edge['relation_label']}" for edge in incoming[:6])
            summary.append(f"入边: {sample}")
        if summary:
            return f"{node_name} 的局部知识如下。{' '.join(summary)}"

    return "暂不支持该问法。可尝试：`二战中使用了哪些克虏伯设计的火炮`、`基于M4谢尔曼底盘改造的火炮，口径最大的是多少`。"
