from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from src.graph_app_utils import (
    answer_question_with_rag,
    build_plot_positions,
    fuzzy_find_name,
    global_subgraph,
    graph_stats,
    load_graph_bundle,
    node_brief,
    one_hop_subgraph,
    parameter_profile,
    relationship_groups,
)


st.set_page_config(page_title="全球火炮知识图谱", page_icon="🎯", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --bg: #f3f5f8;
        --surface: #ffffff;
        --surface-strong: #f8fafc;
        --line: #d9e0ea;
        --line-strong: #b9c4d2;
        --text: #172033;
        --muted: #7a8699;
        --accent: #0f6fff;
        --accent-2: #ff8a1f;
        --steel: #27384f;
    }
    .stApp {
        background:
            linear-gradient(135deg, rgba(15,111,255,0.045) 0 25%, transparent 25% 50%, rgba(39,56,79,0.035) 50% 75%, transparent 75%),
            radial-gradient(circle at 12% 4%, rgba(15,111,255,0.14), transparent 24%),
            radial-gradient(circle at 88% 0%, rgba(255,138,31,0.10), transparent 22%),
            var(--bg);
        background-size: 26px 26px, auto, auto, auto;
        color: var(--text);
    }
    .block-container {
        padding-top: 3.9rem;
        padding-bottom: 2.2rem;
        max-width: 1500px;
    }
    section[data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 15% 0%, rgba(15,111,255,0.12), transparent 24%),
            linear-gradient(180deg, #fbfdff 0%, #eef3f9 100%);
        border-right: 1px solid var(--line);
        box-shadow: 18px 0 42px rgba(39, 56, 79, 0.08);
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 3.1rem;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: var(--steel);
        letter-spacing: -0.02em;
        font-weight: 900;
    }
    .sidebar-brand {
        border: 1px solid #d7e2ef;
        background: rgba(255,255,255,0.78);
        border-radius: 18px;
        padding: 0.9rem 0.95rem;
        margin-bottom: 0.85rem;
        box-shadow: 0 12px 28px rgba(39, 56, 79, 0.06);
    }
    .sidebar-kicker {
        color: var(--accent);
        font-size: 0.7rem;
        font-weight: 900;
        letter-spacing: 0.14em;
        text-transform: uppercase;
    }
    .sidebar-title {
        color: var(--text);
        font-size: 1.05rem;
        font-weight: 900;
        margin-top: 0.2rem;
    }
    .sidebar-copy {
        color: var(--muted);
        font-size: 0.78rem;
        line-height: 1.5;
        margin-top: 0.32rem;
    }
    div[role="radiogroup"] label {
        border: 1px solid transparent;
        border-radius: 12px;
        padding: 0.42rem 0.55rem;
        margin-bottom: 0.2rem;
        background: #f6f8fb;
        transition: all 140ms ease;
    }
    div[role="radiogroup"] label:hover {
        border-color: #c7d6ea;
        background: #eef5ff;
    }
    .panel {
        border: 1px solid rgba(185, 196, 210, 0.72);
        background: rgba(255, 255, 255, 0.94);
        border-radius: 18px;
        padding: 1rem 1.15rem;
        box-shadow: 0 14px 34px rgba(39, 56, 79, 0.08);
    }
    .hero-panel {
        position: relative;
        overflow: hidden;
        border-top: 3px solid var(--accent);
    }
    .hero-panel:after {
        content: "";
        position: absolute;
        right: -90px;
        top: -120px;
        width: 280px;
        height: 280px;
        border: 1px solid rgba(15,111,255,0.16);
        border-radius: 50%;
        box-shadow: inset 0 0 0 18px rgba(15,111,255,0.035);
    }
    .eyebrow {
        color: var(--accent);
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        margin-bottom: 0.25rem;
    }
    .hero-title {
        font-size: 2.15rem;
        font-weight: 900;
        letter-spacing: -0.04em;
        color: var(--text);
        margin-bottom: 0.35rem;
    }
    .hero-sub {
        color: var(--muted);
        font-size: 0.98rem;
        max-width: 980px;
        white-space: nowrap; /* 强制不换行 */
    }
    .stat-card {
        display: flex;
        align-items: center;
        gap: 0.78rem;
        min-height: 78px;
        padding: 0.82rem 0.95rem;
    }
    .stat-icon {
        width: 42px;
        height: 42px;
        border-radius: 14px;
        display: grid;
        place-items: center;
        color: #ffffff;
        font-weight: 900;
        background: linear-gradient(135deg, var(--steel), var(--accent));
        box-shadow: 0 9px 18px rgba(15, 111, 255, 0.18);
    }
    .stat-value {
        font-size: 1.7rem;
        font-weight: 900;
        color: var(--text);
        line-height: 1;
        letter-spacing: -0.03em;
    }
    .stat-label {
        color: var(--muted);
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.3rem;
    }
    .weapon-title {
        font-size: 1.82rem;
        font-weight: 900;
        letter-spacing: -0.035em;
        color: var(--text);
        margin: 0.2rem 0 0.85rem 0;
    }
    .attribute-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.55rem 0.95rem;
        margin-bottom: 1rem;
    }
    .attribute-item {
        border-bottom: 1px solid var(--line);
        padding: 0.48rem 0 0.55rem 0;
    }
    .attribute-key {
        color: var(--muted);
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.08em;
    }
    .attribute-val {
        color: var(--text);
        font-size: 1.02rem;
        font-weight: 850;
        margin-top: 0.14rem;
    }
    .image-frame {
        background: linear-gradient(135deg, #101827, #27384f);
        border: 1px solid #c8d2df;
        border-radius: 16px;
        padding: 8px;
        box-shadow: 0 18px 42px rgba(23, 32, 51, 0.16);
    }
    .image-frame img {
        border-radius: 10px;
        display: block;
    }
    .section-title {
        font-size: 1.02rem;
        font-weight: 900;
        color: var(--steel);
        margin: 0 0 0.72rem 0;
        letter-spacing: -0.01em;
    }
    .progress-row {
        margin: 0 0 0.78rem 0;
    }
    .progress-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 1rem;
        margin-bottom: 0.28rem;
    }
    .progress-label {
        color: var(--muted);
        font-size: 0.82rem;
        font-weight: 750;
    }
    .progress-value {
        color: var(--text);
        font-size: 0.9rem;
        font-weight: 900;
    }
    .progress-track {
        height: 8px;
        border-radius: 999px;
        background: #e8edf4;
        overflow: hidden;
        border: 1px solid #dbe3ee;
    }
    .progress-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, var(--accent), #61a6ff 58%, var(--accent-2));
        box-shadow: 0 0 18px rgba(15, 111, 255, 0.38);
    }
    .relation-pill {
        display: inline-block;
        border: 1px solid #d7e2ef;
        background: #f6f9fd;
        color: #27384f;
        border-radius: 999px;
        padding: 0.26rem 0.58rem;
        margin: 0.12rem 0.16rem 0.2rem 0;
        font-size: 0.82rem;
        font-weight: 700;
    }
    .guide-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.65rem;
        margin: 0.8rem 0 1rem 0;
    }
    .guide-card {
        border: 1px solid #d7e2ef;
        background: linear-gradient(180deg, #ffffff, #f8fbff);
        border-radius: 14px;
        padding: 0.78rem 0.9rem;
    }
    .guide-title {
        color: var(--steel);
        font-size: 0.92rem;
        font-weight: 900;
        margin-bottom: 0.24rem;
    }
    .guide-copy {
        color: var(--muted);
        font-size: 0.8rem;
        line-height: 1.45;
    }
    .detail-title {
        font-size: 1.35rem;
        line-height: 1.2;
        color: var(--text);
        font-weight: 900;
        letter-spacing: -0.03em;
        margin: 0.15rem 0 0.35rem 0;
    }
    .detail-type {
        display: inline-block;
        border-radius: 999px;
        padding: 0.18rem 0.5rem;
        background: #eef5ff;
        color: var(--accent);
        border: 1px solid #cfe2ff;
        font-size: 0.74rem;
        font-weight: 850;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.6rem;
    }
    .hint-box {
        border-left: 3px solid var(--accent);
        background: #f7fbff;
        color: #4b5b72;
        border-radius: 12px;
        padding: 0.72rem 0.9rem;
        font-size: 0.86rem;
        line-height: 1.55;
    }
    .answer-box {
        border: 1px solid #cfe2ff;
        background: linear-gradient(180deg, #ffffff, #f7fbff);
        border-radius: 18px;
        padding: 1rem 1.15rem;
        box-shadow: 0 14px 34px rgba(39, 56, 79, 0.08);
        color: var(--text);
        line-height: 1.75;
        font-size: 0.98rem;
    }
    .filter-panel {
        border: 1px solid #d7e2ef;
        background: rgba(255,255,255,0.78);
        border-radius: 16px;
        padding: 0.72rem 0.9rem;
        margin: 0.85rem 0 0.9rem 0;
        color: var(--muted);
        font-size: 0.84rem;
    }
    .source-line {
        color: var(--muted);
        font-size: 0.82rem;
        margin-top: 0.6rem;
    }
    .retrieval-intro {
        color: var(--text);
        font-size: 0.95rem;
        margin-bottom: 0.8rem;
        line-height: 1.6;
    }
    .retrieval-card {
        border: 1px solid #d7e2ef;
        background: #f9fbfe;
        border-radius: 14px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.7rem;
    }
    .retrieval-card-title {
        font-weight: 600;
        font-size: 1.02rem;
        color: #1a3a5c;
        margin-bottom: 0.5rem;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid #e4ecf4;
    }
    .retrieval-field {
        margin-bottom: 0.4rem;
        font-size: 0.9rem;
        line-height: 1.6;
    }
    .retrieval-field-label {
        display: inline-block;
        font-weight: 600;
        color: #3a6ea5;
        min-width: 5em;
        margin-right: 0.4em;
    }
    .retrieval-field-value {
        color: var(--text);
    }
    .retrieval-tag {
        display: inline-block;
        background: #e8f0fb;
        color: #2c5f8a;
        border-radius: 6px;
        padding: 0.12rem 0.5rem;
        margin: 0.15rem 0.2rem 0.15rem 0;
        font-size: 0.82rem;
    }
    .retrieval-ocr {
        margin-top: 0.5rem;
        padding: 0.6rem 0.8rem;
        background: #ffffff;
        border: 1px solid #e9eff6;
        border-radius: 10px;
        font-size: 0.85rem;
        color: #4a5568;
        line-height: 1.7;
        max-height: 180px;
        overflow-y: auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _format_retrieval_html(answer_text: str) -> str:
    """Parse fallback retrieval text into structured HTML cards."""
    import re
    lines = answer_text.split("\n")
    intro = ""
    blocks_raw = []
    current_block = []

    for line in lines:
        if line.startswith("【火炮】"):
            if current_block:
                blocks_raw.append(current_block)
            current_block = [line]
        elif current_block:
            current_block.append(line)
        else:
            if line.strip():
                intro += line.strip()

    if current_block:
        blocks_raw.append(current_block)

    if not blocks_raw:
        return answer_text.replace("\n", "<br>")

    html_parts = []
    if intro:
        html_parts.append(f'<div class="retrieval-intro">{intro}</div>')

    for block in blocks_raw:
        title = block[0].replace("【火炮】", "").strip()
        attrs = ""
        rels_html = ""
        ocr = ""

        for line in block[1:]:
            if line.startswith("基础属性："):
                raw = line[len("基础属性："):]
                if raw and raw != "无":
                    pairs = [p.strip() for p in raw.split("；") if p.strip()]
                    attrs = "".join(f'<span class="retrieval-tag">{p}</span>' for p in pairs)
            elif line.startswith("图谱关系："):
                raw = line[len("图谱关系："):]
                if raw and raw != "无":
                    pairs = [p.strip() for p in raw.split("；") if p.strip()]
                    rels_html = "".join(f'<span class="retrieval-tag">{p}</span>' for p in pairs)
            elif line.startswith("原书OCR摘录："):
                raw = line[len("原书OCR摘录："):]
                if raw and raw != "无":
                    ocr = raw.replace("\n", "<br>")

        card = f'<div class="retrieval-card"><div class="retrieval-card-title">{title}</div>'
        if attrs:
            card += f'<div class="retrieval-field"><span class="retrieval-field-label">基础属性</span>{attrs}</div>'
        if rels_html:
            card += f'<div class="retrieval-field"><span class="retrieval-field-label">图谱关系</span>{rels_html}</div>'
        if ocr:
            card += f'<div class="retrieval-ocr">{ocr}</div>'
        card += '</div>'
        html_parts.append(card)

    return "\n".join(html_parts)


@st.cache_data(show_spinner=False)
def get_bundle(view_mode: str):
    return load_graph_bundle(view=view_mode)


def render_network(subgraph: dict, center_name: str | None = None, selected_name: str | None = None, key: str = "network"):
    if not subgraph["nodes"]:
        st.info("没有可展示的局部网络。")
        return None

    positions = build_plot_positions(subgraph["nodes"], center_name)
    palette = {
        "Artillery": "#0f6fff",
        "Country": "#27384f",
        "Category": "#ff8a1f",
        "Institution": "#16845b",
        "Designer": "#0b8a9a",
        "Ammunition": "#536dfe",
        "War": "#d13232",
        "Chassis": "#6f7d91",
        "Derivative": "#9c6644",
        "Property": "#7c3aed",
        "SubCategory": "#2563eb",
        "MilitaryBranch": "#b45309",
    }

    fig = go.Figure()
    for edge in subgraph["edges"]:
        x0, y0 = positions[edge["source"]]
        x1, y1 = positions[edge["target"]]
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line={"width": 2.1, "color": "rgba(39, 56, 79, 0.24)"},
                hoverinfo="text",
                text=f"{edge['source']} -[{edge['relation_label']}]-> {edge['target']}",
                showlegend=False,
            )
        )
        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2
        fig.add_trace(
            go.Scatter(
                x=[mid_x],
                y=[mid_y],
                mode="text",
                text=[edge["relation_label"]],
                textfont={"size": 10, "color": "#6f7d91"},
                hoverinfo="skip",
                showlegend=False,
            )
        )

    by_label = {}
    for node in subgraph["nodes"]:
        by_label.setdefault(node["label"], []).append(node)

    for label, items in by_label.items():
        xs = [positions[node["id"]][0] for node in items]
        ys = [positions[node["id"]][1] for node in items]
        texts = [node["name"] for node in items]
        hover = [f"{node['name']}<br>{node['label']}" for node in items]
        sizes = [42 if center_name and node["id"] == center_name else 32 if node["id"] == selected_name else 14 if len(subgraph["nodes"]) > 80 else 21 for node in items]
        customdata = [node["id"] for node in items]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers+text",
                text=texts,
                customdata=customdata,
                textposition="top center",
                hovertext=hover,
                hoverinfo="text",
                marker={
                    "size": sizes,
                    "color": palette.get(label, "#6b7280"),
                    "line": {"width": 3 if node["id"] == selected_name else 2 if center_name and node["id"] == center_name else 1, "color": "#ffffff"},
                },
                name=label,
            )
        )

    fig.update_layout(
        height=620 if len(subgraph["nodes"]) > 80 else 560,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        xaxis={"visible": False, "fixedrange": False},
        yaxis={"visible": False, "fixedrange": False},
        legend={"orientation": "h", "y": 1.04, "x": 0.01},
        font={"color": "#27384f"},
        dragmode="pan",
    )
    config = {
        "displayModeBar": True,
        "scrollZoom": True,
        "doubleClick": "reset",
        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
    }
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        config=config,
        key=key,
        on_select="rerun",
        selection_mode="points",
    )
    points = getattr(event, "selection", {}).get("points", []) if event is not None else []
    if points:
        point = points[0]
        customdata = point.get("customdata")
        if customdata:
            return customdata
        curve_number = point.get("curve_number")
        point_number = point.get("point_number")
        if curve_number is not None and point_number is not None:
            trace = fig.data[curve_number]
            if getattr(trace, "customdata", None) is not None:
                return trace.customdata[point_number]
    return None


def render_parameter_chart(profile: list):
    if not profile:
        st.info("该火炮缺少有效参数。")
        return

    radar_metrics = [item for item in profile if item["key"] in {"caliber", "range", "weight", "rate_of_fire", "length"}]
    if radar_metrics:
        labels = [item["metric"] for item in radar_metrics]
        scores = [item["score"] for item in radar_metrics]
        labels_closed = labels + labels[:1]
        scores_closed = scores + scores[:1]
        fig = go.Figure(
            go.Scatterpolar(
                r=scores_closed,
                theta=labels_closed,
                fill="toself",
                fillcolor="rgba(15, 111, 255, 0.18)",
                line={"color": "#0f6fff", "width": 3},
                marker={"size": 7, "color": "#ff8a1f"},
                name="归一化能力",
            )
        )
        fig.update_layout(
            height=330,
            margin={"l": 20, "r": 20, "t": 18, "b": 18},
            paper_bgcolor="rgba(255,255,255,0)",
            plot_bgcolor="rgba(255,255,255,0)",
            polar={
                "bgcolor": "rgba(248,250,252,0.6)",
                "radialaxis": {"visible": True, "range": [0, 100], "tickfont": {"size": 10, "color": "#7a8699"}},
                "angularaxis": {"tickfont": {"size": 12, "color": "#27384f"}},
            },
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-title">全局水平对比</div>', unsafe_allow_html=True)
    for item in profile:
        st.markdown(
            f"""
            <div class="progress-row">
                <div class="progress-head">
                    <div class="progress-label">{item['metric']}</div>
                    <div class="progress-value">{item['display_value']} {item['unit']}</div>
                </div>
                <div class="progress-track"><div class="progress-fill" style="width:{item['score']}%"></div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_rank_chart(title: str, pairs: list, color: str):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if not pairs:
        st.info("暂无可展示数据。")
        return
    names = [name for name, _ in pairs][::-1]
    values = [value for _, value in pairs][::-1]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            text=values,
            textposition="outside",
            marker={"color": color},
        )
    )
    fig.update_layout(
        height=max(320, 32 * len(pairs)),
        margin={"l": 10, "r": 30, "t": 10, "b": 10},
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        xaxis_title="关联火炮数量",
        font={"color": "#27384f"},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_relation_donut(stats: dict):
    pairs = stats["top_relations"]
    if not pairs:
        st.info("暂无关系数据。")
        return
    labels = [RELATION_DISPLAY.get(name, name) for name, _ in pairs]
    values = [value for _, value in pairs]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.52,
            marker={"colors": ["#0f6fff", "#27384f", "#ff8a1f", "#d13232", "#16845b", "#536dfe", "#6f7d91", "#0b8a9a"]},
        )
    )
    fig.update_layout(
        height=420,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        paper_bgcolor="rgba(255,255,255,0)",
        font={"color": "#27384f"},
    )
    st.plotly_chart(fig, use_container_width=True)


def render_attribute_list(items: list):
    html = ['<div class="attribute-grid">']
    for key, value in items:
        html.append(
            f'<div class="attribute-item"><div class="attribute-key">{key}</div><div class="attribute-val">{value}</div></div>'
        )
    html.append('</div>')
    st.markdown("".join(html), unsafe_allow_html=True)


def render_relation_pills(relation_map: dict):
    if not relation_map:
        st.info("没有提取到可展示的关系。")
        return
    for title, values in relation_map.items():
        st.markdown(f"**{title}**")
        pills = "".join(f'<span class="relation-pill">{value}</span>' for value in values[:12])
        st.markdown(pills, unsafe_allow_html=True)


def render_node_detail(bundle, node_name: str):
    node = bundle.node_index.get(node_name)
    if not node:
        st.info("请选择图中的一个节点查看详情。")
        return

    st.markdown(f'<div class="detail-type">{node["label"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="detail-title">{node_name}</div>', unsafe_allow_html=True)

    if node["label"] == "Artillery":
        render_attribute_list(node_brief(node))
        image_path = node.get("image_path", "")
        if image_path and Path(image_path).exists():
            st.markdown('<div class="image-frame">', unsafe_allow_html=True)
            st.image(image_path, use_column_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        profile = parameter_profile(node)
        if profile:
            st.markdown('<div class="section-title">参数水平</div>', unsafe_allow_html=True)
            for item in profile[:4]:
                st.markdown(
                    f"""
                    <div class="progress-row">
                        <div class="progress-head">
                            <div class="progress-label">{item['metric']}</div>
                            <div class="progress-value">{item['display_value']} {item['unit']}</div>
                        </div>
                        <div class="progress-track"><div class="progress-fill" style="width:{item['score']}%"></div></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        relation_map = relationship_groups(bundle, node_name)
        st.markdown('<div class="section-title">关联知识</div>', unsafe_allow_html=True)
        render_relation_pills(relation_map)
        return

    incoming = bundle.incoming.get(node_name, [])
    outgoing = bundle.outgoing.get(node_name, [])
    related_artillery = [edge["source"] for edge in incoming if edge.get("source_type") == "Artillery"]
    st.markdown(
        f"""
        <div class="hint-box">
            这是一个 <b>{node['label']}</b> 类型节点。它在当前图谱视图中连接了
            <b>{len(incoming)}</b> 条入边和 <b>{len(outgoing)}</b> 条出边。
        </div>
        """,
        unsafe_allow_html=True,
    )
    if related_artillery:
        st.markdown('<div class="section-title">相关火炮</div>', unsafe_allow_html=True)
        pills = "".join(f'<span class="relation-pill">{name}</span>' for name in related_artillery[:18])
        st.markdown(pills, unsafe_allow_html=True)
    if outgoing:
        st.markdown('<div class="section-title">向外关系</div>', unsafe_allow_html=True)
        for edge in outgoing[:8]:
            st.write(f"{edge['relation_label']} → {edge['target']}")
    if incoming:
        st.markdown('<div class="section-title">向内关系</div>', unsafe_allow_html=True)
        for edge in incoming[:8]:
            st.write(f"{edge['source']} → {edge['relation_label']}")


RELATION_DISPLAY = {
    "DEVELOPED_IN": "研发国家",
    "IS_TYPE_OF": "类型",
    "DESIGNED_BY": "设计方",
    "USES_AMMO": "弹药",
    "DERIVED_FROM": "衍生型号",
    "PARTICIPATED_IN": "参战",
    "USES_CHASSIS": "底盘",
    "EQUIPPED_BY": "装备国家",
}


bundle_view_options = {
    "可信视图": "trusted",
    "原始全量图谱": "full",
}
with st.sidebar:
    selected_view_label = st.radio("数据视图", list(bundle_view_options.keys()), index=0)
view_mode = bundle_view_options[selected_view_label]
bundle = get_bundle(view_mode)
stats = graph_stats(bundle)
view_copy = {
    "trusted": {
        "hero": "清洗后的可信视图聚焦核心实体与高价值关系，突出武器、国家、战争、工业机构与底盘平台之间的知识网络。",
        "node_label": "可信节点",
        "edge_label": "可信关系",
        "network_label": "可信一跳网络",
        "source_caption": "数据源：《全球火炮鉴赏指南》OCR 正文 + 清洗后的知识图谱关系。",
        "explore_help": "留空时展示全部可信节点和关系；输入火炮、国家、战争、机构、底盘或弹药名称后展示局部关系。",
        "global_title": "全局可信图谱",
    },
    "full": {
        "hero": "原始全量图谱覆盖全部人工构建节点与关系，规模更完整，也会保留更多未清洗的关系与实体类型。",
        "node_label": "全量节点",
        "edge_label": "全量关系",
        "network_label": "一跳网络",
        "source_caption": "数据源：《全球火炮鉴赏指南》OCR 正文 + 原始人工构建知识图谱。",
        "explore_help": "留空时展示全量图谱；输入火炮、国家、战争、机构、底盘或弹药名称后可聚焦局部关系。",
        "global_title": "全局原始图谱",
    },
}[view_mode]
if "explore_center" not in st.session_state:
    st.session_state.explore_center = None
if "explore_selected" not in st.session_state:
    st.session_state.explore_selected = None

st.markdown(
    f"""
    <div class="panel hero-panel">
        <div class="eyebrow">Artillery Knowledge Graph</div>
        <div class="hero-title">全球火炮知识图谱</div>
        <div class="hero-sub">
            {view_copy['hero']}
            当前可视节点 <b>{stats['node_total']}</b>，关系 <b>{stats['edge_total']}</b>。
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-kicker">Navigation Console</div>
            <div class="sidebar-title">知识图谱导航</div>
            <div class="sidebar-copy">切换展示视角：武器详情、全局关系、宏观统计与知识库问答。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"当前数据视图：{selected_view_label}")
    mode = st.radio("查看模式", ["武器详情", "图谱探索", "宏观洞察", "智能问答"], index=0)
    st.caption(view_copy["source_caption"])

category_options = ["全部"] + sorted({bundle.node_index[name].get("category", "未知") for name in bundle.artillery_names})
selected_category = "全部"

filtered_artillery = [
    name
    for name in bundle.artillery_names
    if selected_category == "全部" or bundle.node_index[name].get("category", "未知") == selected_category
]

stat_cols = st.columns(4)
stat_items = [
    (stat_cols[0], stats["node_total"], view_copy["node_label"], "N"),
    (stat_cols[1], stats["edge_total"], view_copy["edge_label"], "R"),
    (stat_cols[2], len(bundle.artillery_names), "火炮实体", "A"),
    (stat_cols[3], len(bundle.label_names.get("War", [])), "战争节点", "W"),
]
for col, value, label, icon in stat_items:
    with col:
        st.markdown(
            f"""
            <div class="panel stat-card">
                <div class="stat-icon">{icon}</div>
                <div>
                    <div class="stat-label">{label}</div>
                    <div class="stat-value">{value}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

if mode == "武器详情":
    filter_left, filter_right = st.columns([0.72, 1.28])
    with filter_left:
        selected_category = st.selectbox("🔎 类别过滤 / 搜索", category_options, index=0)
    filtered_artillery = [
        name
        for name in bundle.artillery_names
        if selected_category == "全部" or bundle.node_index[name].get("category", "未知") == selected_category
    ]
    with filter_right:
        st.markdown(
            f'<div class="filter-panel">当前筛选：<b>{selected_category}</b> · 可选火炮 <b>{len(filtered_artillery)}</b> 门。该筛选仅影响本页武器详情。</div>',
            unsafe_allow_html=True,
        )

    default_index = filtered_artillery.index(filtered_artillery[0]) if filtered_artillery else 0
    selected_name = st.selectbox("选择火炮实体", filtered_artillery, index=default_index)
    artillery = bundle.node_index[selected_name]
    profile = parameter_profile(artillery)
    relation_map = relationship_groups(bundle, selected_name)
    subgraph = one_hop_subgraph(bundle, selected_name)

    top_left, top_right = st.columns([1.15, 1])
    with top_left:
        st.markdown(f'<div class="weapon-title">{selected_name}</div>', unsafe_allow_html=True)
        brief = node_brief(artillery)
        render_attribute_list(brief)
        image_path = artillery.get("image_path", "")
        if image_path and Path(image_path).exists():
            st.markdown('<div class="image-frame">', unsafe_allow_html=True)
            st.image(image_path, use_column_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("当前实体没有对齐到可用图片。")
    with top_right:
        st.markdown('<div class="section-title">综合能力雷达 / 参数水平</div>', unsafe_allow_html=True)
        render_parameter_chart(profile)

    rel_left, rel_right = st.columns([0.92, 1.08])
    with rel_left:
        st.markdown('<div class="section-title">核心关系</div>', unsafe_allow_html=True)
        render_relation_pills(relation_map)
    with rel_right:
        st.markdown(f'<div class="section-title">{view_copy["network_label"]}</div>', unsafe_allow_html=True)
        render_network(subgraph, selected_name)

elif mode == "图谱探索":
    st.markdown("### 图谱探索：从一个节点理解整张知识网")
    st.markdown(
        """
        <div class="hint-box">
            这个页面不是传统表格，而是一个“关系地图”：左侧默认展示当前视图下的节点与关系，右侧展示你选中节点的详细信息。
            如果你想聚焦某个对象，可以在搜索框中输入“二战”“美国”或任意一门火炮名称切换为局部视图。
        </div>
        <div class="guide-grid">
            <div class="guide-card"><div class="guide-title">火炮节点</div><div class="guide-copy">查看某门火炮的研发国家、类别、弹药、战争、底盘和衍生型号。</div></div>
            <div class="guide-card"><div class="guide-title">战争 / 国家</div><div class="guide-copy">查看某场战争或某个国家关联了哪些火炮装备。</div></div>
            <div class="guide-card"><div class="guide-title">机构 / 底盘</div><div class="guide-copy">观察工业机构、设计师、底盘平台与装备之间的连接。</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    quick_options = [
        name
        for name in ["海湾战争", "二战", "美国", "苏联", "榴弹炮", "克虏伯", "M4谢尔曼底盘"]
        if name in bundle.node_index
    ]
    if filtered_artillery:
        quick_options.extend(filtered_artillery[:8])
    quick_options = list(dict.fromkeys(quick_options))

    control_left, control_right = st.columns([1, 1])
    with control_left:
        search_text = st.text_input(
            "搜索中心节点（留空显示全图）",
            value=st.session_state.explore_center or "",
            help=view_copy["explore_help"],
        )
    center_name = fuzzy_find_name(bundle, search_text) if search_text else None
    if not search_text:
        st.session_state.explore_center = None
        st.session_state.explore_selected = None
    elif center_name:
        st.session_state.explore_center = center_name
    if search_text and not center_name:
        st.warning("没有找到匹配节点，请尝试：海湾战争、美国、榴弹炮、克虏伯、M4谢尔曼底盘。")
    else:
        subgraph = one_hop_subgraph(bundle, center_name, max_nodes=18) if center_name else global_subgraph(bundle)
        node_options = [node["id"] for node in subgraph["nodes"]]
        fallback_detail = center_name if center_name else (bundle.artillery_names[0] if bundle.artillery_names[0] in node_options else node_options[0])
        default_detail = st.session_state.explore_selected if st.session_state.explore_selected in node_options else fallback_detail
        with control_right:
            selected_node = st.selectbox("选择图中节点查看详情", node_options, index=node_options.index(default_detail))
        st.session_state.explore_selected = selected_node

        if quick_options:
            selected_quick = st.selectbox("推荐探索入口", quick_options, index=0)
            st.caption(f"提示：复制 `{selected_quick}` 到搜索框可切换为以它为中心的局部视图；清空搜索框可回到全图。")

        graph_col, detail_col = st.columns([1.35, 0.85])
        with graph_col:
            if center_name:
                center = bundle.node_index[center_name]
                st.markdown(f'<div class="section-title">局部视图：{center_name} · {center["label"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="section-title">{view_copy["global_title"]}：{len(subgraph["nodes"])} 个节点 · {len(subgraph["edges"])} 条关系</div>', unsafe_allow_html=True)
            clicked_node = render_network(subgraph, center_name, selected_node, key="explore_graph")
            if clicked_node and clicked_node in bundle.node_index:
                st.session_state.explore_center = clicked_node
                st.session_state.explore_selected = clicked_node
                if clicked_node != center_name:
                    if hasattr(st, "rerun"):
                        st.rerun()
                    else:
                        st.experimental_rerun()
                selected_node = clicked_node
        with detail_col:
            st.markdown('<div class="section-title">节点详情</div>', unsafe_allow_html=True)
            render_node_detail(bundle, st.session_state.explore_selected or selected_node)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**当前图谱能探索的节点类型**")
            for label, count in stats["top_labels"]:
                st.write(f"{label}: {count}")
        with c2:
            st.markdown("**当前图谱能探索的关系类型**")
            for rel, count in stats["top_relations"]:
                st.write(f"{RELATION_DISPLAY.get(rel, rel)}: {count}")

elif mode == "宏观洞察":
    st.markdown("### 宏观军事装备图谱洞察")
    st.caption("从国家、类别、战争和工业机构四个角度观察火炮知识网络的结构分布。")

    left, right = st.columns([1, 1])
    with left:
        render_relation_donut(stats)
    with right:
        render_rank_chart("国家装备/研发规模", stats["top_countries"], "#315f85")

    c1, c2, c3 = st.columns(3)
    with c1:
        render_rank_chart("火炮类别分布", stats["top_categories"], "#9a5b2a")
    with c2:
        render_rank_chart("战争关联热度", stats["top_wars"], "#b42318")
    with c3:
        render_rank_chart("工业机构关联度", stats["top_institutions"], "#1d6f42")

else:
    st.markdown("### 火炮知识库智能问答")
    st.markdown(
        """
        <div class="hint-box">
            这里会先从《全球火炮鉴赏指南》的 OCR 正文和当前知识图谱视图中检索证据，再调用 DeepSeek 生成回答。
            如果问题与本书知识库无关，系统会拒绝回答，避免泛泛聊天或编造内容。
        </div>
        """,
        unsafe_allow_html=True,
    )
    api_key = st.text_input("DeepSeek API Key（也可设置环境变量 DEEPSEEK_API_KEY）", type="password", placeholder="sk-...")
    question = st.text_area(
        "输入你的问题",
        value="M109自行榴弹炮有什么特点？",
        height=130,
        help="建议询问火炮性能、型号、参战、国家、底盘、弹药、研发机构等与本书相关的问题。",
    )
    examples = [
        "二战中出现了哪些火炮？",
        "M109自行榴弹炮有什么特点？",
        "哪些火炮和克虏伯有关？",
        "基于M4谢尔曼底盘的火炮有哪些？",
    ]
    st.caption("示例问题：" + " / ".join(f"`{item}`" for item in examples))

    if st.button("检索知识库并回答", type="primary"):
        with st.spinner("正在检索知识库并生成回答..."):
            result = answer_question_with_rag(bundle, question, api_key=api_key or None)
        st.markdown("### 回答")
        if not result.get("used_deepseek") and "【火炮】" in result["answer"]:
            st.markdown(f'<div class="answer-box">{_format_retrieval_html(result["answer"])}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="answer-box">{result["answer"].replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
        if result.get("sources"):
            st.markdown(
                f'<div class="source-line">参考来源：{"；".join(result["sources"])} · {"DeepSeek生成" if result.get("used_deepseek") else "本地检索摘要"}</div>',
                unsafe_allow_html=True,
            )
        elif not result.get("is_relevant"):
            st.caption("未命中知识库相关内容。")
