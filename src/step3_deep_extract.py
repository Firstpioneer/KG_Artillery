# -*- coding: utf-8 -*-
"""
步骤3: 规则 + LLM 混合深度抽取
目标: 提取 Institution, Designer, Ammunition, Derivative, War, Chassis 实体
      及 DESIGNED_BY, USES_AMMO, DERIVED_FROM, PARTICIPATED_IN, USES_CHASSIS 关系
策略: 先用规则从OCR文本中提取结构化信息,再用LLM补充提取复杂关系
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = "../data/output"

# ==========================================
# 第一部分: 基于规则的抽取
# ==========================================

# 参战冲突关键词
WAR_KEYWORDS = {
    "二战": ["二战", "第二次世界大战"],
    "一战": ["一战", "第一次世界大战"],
    "海湾战争": ["海湾战争", "沙漠风暴"],
    "朝鲜战争": ["朝鲜战争", "韩战"],
    "越南战争": ["越南战争", "越战"],
    "阿富汗战争": ["阿富汗战争"],
    "伊拉克战争": ["伊拉克战争"],
    "冷战": ["冷战"],
    "科索沃战争": ["科索沃战争"],
    "中东战争": ["中东战争", "中东地区的战争"],
    "印巴战争": ["印巴战争"],
    "苏芬战争": ["苏芬战争", "冬季战争"],
    "两伊战争": ["两伊战争"],
    "车臣战争": ["车臣战争"],
    "叙利亚内战": ["叙利亚内战"],
    "俄乌冲突": ["俄乌"],
    "马岛战争": ["福克兰战争", "马岛战争"],
    "太平洋战争": ["太平洋战争", "太平洋战役"],
    "诺曼底登陆": ["诺曼底"],
    "苏德战争": ["苏德战争", "卫国战争", "东线"],
    "第三次中东战争": ["六日战争"],
    "第四次中东战争": ["赎罪日战争"],
    "黎巴嫩战争": ["黎巴嫩战争"],
    "波黑战争": ["波黑战争"],
    "利比亚战争": ["利比亚战争"],
    "也门内战": ["也门"],
    "巴以冲突": ["巴以"],
    "克什米尔冲突": ["克什米尔"],
    "柬埔寨内战": ["柬埔寨"],
    "安哥拉内战": ["安哥拉"],
    "斯里兰卡内战": ["斯里兰卡内战"],
    "乌克兰冲突": ["乌克兰冲突", "顿巴斯"],
    "纳卡冲突": ["纳卡", "卡拉巴赫"],
}

# 研发机构/设计局关键词
INSTITUTION_KEYWORDS = {
    "克虏伯": ["克虏伯"],
    "莱茵金属": ["莱茵金属"],
    "凯迪拉克": ["凯迪拉克"],
    "BAE系统公司": ["BAE系统"],
    "韦斯特维尔特公司": ["韦斯特维尔特"],
    "乌拉尔运输机械设计局": ["乌拉尔运输机器设计局", "乌拉尔运输机械", "乌拉尔设计局"],
    "莫托维利哈工厂": ["莫托维利哈"],
    "格拉宾设计局": ["格拉宾"],
    "博福斯公司": ["博福斯"],
    "奥托梅莱拉": ["奥托梅莱拉"],
    "莱茵金属防空公司": ["莱茵金属防空"],
    "厄利孔公司": ["厄利孔"],
    "赫希施泰因工厂": ["赫希施泰因"],
    "尼斯特罗夫工厂": ["尼斯特罗夫"],
    "HMWF联合体": ["HMWF"],
    "洛克希德": ["洛克希德"],
    "通用动力": ["通用动力"],
    "雷神公司": ["雷神"],
    "波音公司": ["波音"],
    "马里兰兵工厂": ["马里兰兵工厂"],
    "岩岛兵工厂": ["岩岛兵工厂"],
    "沃特弗利特兵工厂": ["沃特弗利特"],
    "FMC公司": ["FMC"],
    "联合防务公司": ["联合防务"],
    "标致公司": ["标致"],
    "GIAT工业": ["GIAT"],
    "克劳斯-玛菲": ["克劳斯-玛菲", "克劳斯玛菲"],
    "瓦格纳兵工厂": ["瓦格纳"],
    "斯柯达": ["斯柯达"],
    "布尔公司": ["布尔公司"],
    "德拉伦": ["德拉伦"],
    "佩内明德": ["佩内明德"],
    "阿尔维斯": ["阿尔维斯"],
    "维克斯": ["维克斯"],
    "皇家兵工厂": ["皇家兵工厂"],
    "马可尼": ["马可尼"],
    "诺基亚": ["诺基亚"],
    "萨博": ["萨博"],
    "三菱重工": ["三菱重工"],
    "日本制钢所": ["日本制钢所"],
    "小松制作所": ["小松制作所"],
    "韩华防务": ["韩华"],
    "印度兵工厂": ["印度兵工厂", "兵工厂委员会"],
    "阿维布拉斯公司": ["阿维布拉斯"],
    "太空研究组织": ["太空研究组织"],
    "巴西宇航工业": ["巴西宇航"],
    "扎斯塔瓦": ["扎斯塔瓦"],
    "阿森纳": ["阿森纳"],
}

# 底盘/平台关键词
CHASSIS_KEYWORDS = {
    "M4谢尔曼底盘": ["M4谢尔曼", "谢尔曼坦克", "谢尔曼底盘", "M4中型坦克"],
    "M113底盘": ["M113底盘", "M113装甲车"],
    "M2布雷德利底盘": ["M2布雷德利", "M2步兵战车", "M2装甲车"],
    "T-34底盘": ["T-34底盘", "T-34坦克"],
    "T-80底盘": ["T-80坦克的底盘", "T-80底盘", "T-80坦克"],
    "四号坦克底盘": ["四号坦克底盘", "PzKpfw IV", "四号坦克"],
    "豹1底盘": ["豹1底盘", "豹1坦克"],
    "豹2底盘": ["豹2底盘", "豹2坦克"],
    "T-72底盘": ["T-72底盘", "T-72坦克"],
    "BMD底盘": ["BMD底盘", "BMD空降战车"],
    "BMP底盘": ["BMP底盘", "BMP步兵战车"],
    "MAZ卡车": ["MAZ卡车", "MAZ-543", "MAZ-7911"],
    "乌拉尔卡车": ["乌拉尔卡车"],
    "AMX-10底盘": ["AMX-10底盘"],
    "LAV-25底盘": ["LAV-25底盘"],
    "PT-76底盘": ["PT-76"],
    "SU-76底盘": ["SU-76"],
    "三号坦克底盘": ["三号坦克", "PzKpfw III"],
    "追猎者底盘": ["追猎者"],
    "FMTV卡车": ["FMTV"],
    "HEMTT卡车": ["HEMTT"],
    "M109底盘": ["M109底盘"],
    "2S1底盘": ["2S1"],
    "BTR底盘": ["BTR"],
    "猛士底盘": ["猛士"],
    "奔驰底盘": ["奔驰"],
    "普拉特底盘": ["普拉特"],
    "ZIL卡车": ["ZIL"],
    "GAZ卡车": ["GAZ"],
    "KrAZ卡车": ["KrAZ"],
}

# 弹药关键词
AMMO_KEYWORDS = {
    "高爆弹": ["高爆弹", "榴弹"],
    "火箭增程弹": ["火箭增程弹"],
    "子母弹": ["子母弹", "集束弹"],
    "照明弹": ["照明弹"],
    "烟幕弹": ["烟幕弹", "发烟弹"],
    "穿甲弹": ["穿甲弹"],
    "破甲弹": ["破甲弹", "HEAT"],
    "碎甲弹": ["碎甲弹", "HESH"],
    "制导炮弹": ["制导炮弹", "神剑", "Excalibur", "铜斑蛇", "Copperhead"],
    "炮射导弹": ["炮射导弹"],
    "核炮弹": ["核炮弹"],
    "化学弹": ["化学弹"],
    "燃烧弹": ["燃烧弹"],
    "白磷弹": ["白磷弹"],
    "混凝土破坏弹": ["混凝土破坏弹"],
    "半穿甲弹": ["半穿甲弹"],
    "杀伤弹": ["杀伤弹"],
    "宣传弹": ["宣传弹"],
    "训练弹": ["训练弹"],
    "曳光弹": ["曳光弹"],
    "脱壳穿甲弹": ["脱壳穿甲弹", "APFSDS", "尾翼稳定脱壳"],
    "钨芯弹": ["钨芯"],
    "贫铀弹": ["贫铀"],
    "反雷达弹": ["反雷达"],
    "激光制导炮弹": ["激光制导"],
    "卫星制导炮弹": ["卫星制导", "GPS制导"],
}

# 设计师关键词
DESIGNER_KEYWORDS = {
    "格拉宾": ["格拉宾"],
    "维克多·马克洛夫": ["维克多·马克洛夫"],
    "斐迪南·保时捷": ["保时捷博士", "斐迪南·保时捷"],
    "阿尔弗雷德·克虏伯": ["阿尔弗雷德·克虏伯"],
}


def rule_extract_wars(text, weapon_name):
    found = []
    for war_name, keywords in WAR_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                found.append(war_name)
                break
    return found


def rule_extract_institutions(text, weapon_name):
    found = []
    for inst_name, keywords in INSTITUTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                found.append(inst_name)
                break
    return found


def rule_extract_chassis(text, weapon_name):
    found = []
    for chassis_name, keywords in CHASSIS_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                found.append(chassis_name)
                break
    return found


def rule_extract_ammo(text, weapon_name):
    found = []
    for ammo_name, keywords in AMMO_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                found.append(ammo_name)
                break
    return found


def rule_extract_designers(text, weapon_name):
    found = []
    for designer_name, keywords in DESIGNER_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                found.append(designer_name)
                break
    return found


def rule_extract_derivatives(text, weapon_name):
    """从OCR文本中提取衍生型号表格
    OCR把表格拆成了单行: 型号一行,描述一行交替出现
    例如: M1\n基本型\nM1A1\n改进型...
    也兼容同行格式: M109A1  换装M126A1榴弹炮
    """
    found = []
    idx = text.find("衍生型号")
    if idx < 0:
        return found

    section = text[idx:]
    end_markers = ["服役记录", "10秒速识", "性能解析", "武器构造", "全球火炮鉴赏指南"]
    end_pos = len(section)
    for marker in end_markers:
        pos = section.find(marker, 10)
        if 0 < pos < end_pos:
            end_pos = pos
    section = section[:end_pos]

    lines = [l.strip() for l in section.strip().split('\n') if l.strip()]

    # 跳过标题行
    i = 0
    while i < len(lines):
        if lines[i] == "衍生型号" or (lines[i] == "型号" and i + 1 < len(lines) and lines[i+1] == "特点"):
            i += 1
            continue
        if lines[i] == "特点":
            i += 1
            continue
        break

    # 尝试同行格式: "M109A1  换装M126A1榴弹炮"
    same_line_mode = False
    for line in lines[i:i+3]:
        parts = re.split(r'\s{2,}|\t', line)
        if len(parts) >= 2:
            same_line_mode = True
            break

    if same_line_mode:
        for line in lines[i:]:
            if any(m in line for m in ["全球火炮", "Chapter", "第", "版"]):
                continue
            parts = re.split(r'\s{2,}|\t', line)
            if len(parts) >= 2:
                model_name = parts[0].strip()
                desc = " ".join(parts[1:]).strip()
                if model_name and re.search(r'[A-Za-z0-9一-鿿]', model_name):
                    # 过滤掉页码/纯数字等噪声
                    if model_name.isdigit() and len(model_name) <= 4:
                        continue
                    if len(model_name) > 50:
                        continue
                    found.append({"name": model_name, "description": desc})
    else:
        # 交替行模式: 型号一行,描述一行
        # 型号行的特征: 较短, 含字母数字, 不以中文长句开头
        # 描述行的特征: 以中文开头或包含"型"/"改进"等
        while i < len(lines):
            line = lines[i]
            # 跳过无关行
            if any(m in line for m in ["全球火炮", "Chapter", "第", "版"]):
                i += 1
                continue
            # 判断是否为型号行: 含英文字母/数字且较短(<=30字符)
            is_model_line = (len(line) <= 30 and re.search(r'[A-Za-z0-9\-]', line)
                             and not re.match(r'^[一-龥]{3,}', line))
            if is_model_line:
                model_name = line.strip()
                desc = ""
                # 下一行可能是描述
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_is_model = (len(next_line) <= 30 and re.search(r'[A-Za-z0-9\-]', next_line)
                                     and not re.match(r'^[一-龥]{3,}', next_line))
                    if not next_is_model and not any(m in next_line for m in ["全球火炮", "Chapter", "第"]):
                        desc = next_line.strip()
                        i += 1
                # 过滤掉页码/纯数字噪声
                if model_name.isdigit() and len(model_name) <= 4:
                    i += 1
                    continue
                if len(model_name) > 50:
                    i += 1
                    continue
                found.append({"name": model_name, "description": desc})
            i += 1

    # 二次过滤: 去掉不像型号的条目
    cleaned = []
    for item in found:
        name = item["name"]
        # 至少包含一个字母或数字
        if not re.search(r'[A-Za-z0-9]', name):
            continue
        # 排除纯数字页码
        if re.match(r'^\d{1,4}$', name):
            continue
        # 排除过长的描述性文字(可能误匹配)
        if len(name) > 40:
            continue
        # 排除含大量中文的行(可能是描述被误识别为型号)
        cn_chars = len(re.findall(r'[一-鿿]', name))
        if cn_chars > len(name) * 0.5 and len(name) > 10:
            continue
        cleaned.append(item)

    return cleaned


def rule_extract_equipped_by(text, weapon_name):
    """从服役记录中提取出口/装备国家"""
    found = []
    # 查找"服役记录"段落
    idx = text.find("服役记录")
    if idx < 0:
        return found

    section = text[idx:idx+500]

    # 查找"出口到XXX" 或 "装备了XXX" 或 "XXX也装备"
    export_patterns = [
        r'出口到[了]?([一-龥]+(?:、[一-龥]+)*)',
        r'装备[了]?([一-龥]+(?:、[一-龥]+)*)',
    ]
    # 常见国家名(简短匹配)
    nation_names = ["日本", "德国", "英国", "法国", "韩国", "印度", "巴西", "意大利",
                    "瑞典", "瑞士", "波兰", "土耳其", "以色列", "埃及", "伊拉克",
                    "伊朗", "沙特", "泰国", "澳大利亚", "加拿大", "荷兰", "比利时",
                    "挪威", "丹麦", "西班牙", "葡萄牙", "希腊", "芬兰", "阿根廷",
                    "智利", "巴基斯坦", "马来西亚", "印尼", "菲律宾", "南非",
                    "尼日利亚", "摩洛哥", "约旦", "科威特", "阿联酋", "卡塔尔",
                    "阿曼", "巴林", "台湾", "新加坡", "新西兰"]

    for nation in nation_names:
        if nation in section:
            found.append(nation)

    return list(set(found))


def rule_extract_all(weapon_name, text):
    wars = rule_extract_wars(text, weapon_name)
    institutions = rule_extract_institutions(text, weapon_name)
    chassis = rule_extract_chassis(text, weapon_name)
    ammo = rule_extract_ammo(text, weapon_name)
    derivatives = rule_extract_derivatives(text, weapon_name)
    designers = rule_extract_designers(text, weapon_name)
    equipped_countries = rule_extract_equipped_by(text, weapon_name)
    # 子类别特征词
    SUBTYPE_KEYWORDS = {
        "自行火炮": ["自行榴弹炮", "自行迫击炮", "自行火箭炮", "自行反坦克炮", "自行防空炮", "自行高射炮", "自走榴弹炮"],
        "牵引火炮": ["牵引榴弹炮", "牵引迫击炮", "牵引式"],
        "车载火炮": ["车载式", "车载型", "卡车炮"],
        "轻型火炮": ["轻型", "轻量化"],
        "重型火炮": ["重型"],
        "超重型火炮": ["超重型"],
        "空降火炮": ["空降", "空投"],
        "两栖火炮": ["两栖", "浮渡", "浮游能力"],
        "山地火炮": ["山地"],
        "多管火箭炮": ["多管"],
        "轮式自行火炮": ["轮式自行"],
        "高射炮": ["高射炮", "防空炮"],
        "舰炮": ["舰炮", "舰载"],
    }
    subtypes = []
    for subtype_name, kws in SUBTYPE_KEYWORDS.items():
        for kw in kws:
            if kw in text or kw in weapon_name:
                subtypes.append(subtype_name)
                break

    # 服役军种
    MILITARY_BRANCH_KEYWORDS = {
        "陆军": ["陆军", "步兵师", "装甲师", "炮兵师", "炮兵旅", "炮兵团"],
        "海军": ["海军陆战队", "海军", "舰载"],
        "空军": ["空军", "空降师", "空中突击师"],
        "海军陆战队": ["海军陆战队"],
    }
    branches = []
    for branch_name, kws in MILITARY_BRANCH_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                branches.append(branch_name)
                break

    return {
        "wars": wars,
        "institutions": institutions,
        "chassis": chassis,
        "ammo": ammo,
        "derivatives": derivatives,
        "designers": designers,
        "equipped_countries": equipped_countries,
        "subtypes": subtypes,
        "branches": branches,
    }


# ==========================================
# 第二部分: LLM深度抽取
# ==========================================

def llm_extract(weapon_name, text, api_key=None, model_name="qwen-plus"):
    try:
        import openai
    except ImportError:
        return None

    if not api_key:
        api_key = os.environ.get("DASHSCOPE_API_KEY", os.environ.get("QWEN_API_KEY", ""))
        if not api_key:
            return None

    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    prompt = f"""你是一个军事数据抽取专家。请阅读以下关于"{weapon_name}"的文本，提取相关信息。

只能从以下实体类别中选择：研发机构、弹药类型、衍生型号、参战冲突、底盘平台、设计师。

输出严格的JSON格式，包含一个"relations"数组，每条记录：
- source: "{weapon_name}"
- relation: 关系类型(DESIGNED_BY/USES_AMMO/DERIVED_FROM/PARTICIPATED_IN/USES_CHASSIS)
- target: 目标实体名称
- target_type: 目标类型(Institution/Designer/Ammunition/Derivative/War/Chassis)

对于DERIVED_FROM关系，source是衍生型号名，target是"{weapon_name}"。

请只从文本中提取确实存在的信息，不要编造。如果没有相关信息，返回空数组。

文本内容：
{text[:3000]}"""

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = response.choices[0].message.content
        # 尝试提取JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            if isinstance(result, dict) and "relations" in result:
                return result["relations"]
        # 也尝试直接解析为数组
        arr_match = re.search(r'\[[\s\S]*\]', content)
        if arr_match:
            return json.loads(arr_match.group())
        return None
    except Exception as e:
        print(f"[ERROR] LLM抽取失败 ({weapon_name}): {e}")
        return None


def main():
    print("=" * 60)
    print("步骤3: 规则 + LLM 混合深度抽取")
    print("=" * 60)

    # 加载step2结果
    with open(os.path.join(OUTPUT_DIR, "step2_ocr_extract.json"), "r", encoding="utf-8") as f:
        step2_data = json.load(f)

    with open(os.path.join(OUTPUT_DIR, "step2_weapon_full_texts.json"), "r", encoding="utf-8") as f:
        weapon_texts = json.load(f)

    # 检查LLM API
    api_key = os.environ.get("DASHSCOPE_API_KEY", os.environ.get("QWEN_API_KEY", ""))
    use_llm = bool(api_key)
    if use_llm:
        print(f"  LLM API密钥已设置,将进行混合抽取")
    else:
        print(f"  未设置LLM API密钥(DASHSCOPE_API_KEY),仅使用规则抽取")

    # 全局实体收集
    global_entities = {
        "Institution": set(),
        "Designer": set(),
        "Ammunition": set(),
        "Derivative": set(),
        "War": set(),
        "Chassis": set(),
        "Country": set(),  # 出口国也加入
        "SubCategory": set(),  # 子类别
        "MilitaryBranch": set(),  # 服役军种
        "Property": set(),  # 属性值
    }
    global_relations = []

    artillery_data = step2_data["artillery"]
    processed = 0

    for art in artillery_data:
        weapon_name = art["name"]
        text = weapon_texts.get(weapon_name, "")
        if not text:
            continue

        # 规则抽取
        rule_result = rule_extract_all(weapon_name, text)

        # LLM抽取
        llm_result = None
        if use_llm:
            llm_result = llm_extract(weapon_name, text, api_key=api_key)

        # --- 合并规则结果 ---
        # 参战冲突
        for war in rule_result["wars"]:
            global_entities["War"].add(war)
            global_relations.append({
                "source": weapon_name,
                "source_type": "Artillery",
                "relation": "PARTICIPATED_IN",
                "target": war,
                "target_type": "War",
                "method": "rule",
            })

        # 研发机构
        for inst in rule_result["institutions"]:
            global_entities["Institution"].add(inst)
            global_relations.append({
                "source": weapon_name,
                "source_type": "Artillery",
                "relation": "DESIGNED_BY",
                "target": inst,
                "target_type": "Institution",
                "method": "rule",
            })

        # 设计师
        for designer in rule_result["designers"]:
            global_entities["Designer"].add(designer)
            global_relations.append({
                "source": weapon_name,
                "source_type": "Artillery",
                "relation": "DESIGNED_BY",
                "target": designer,
                "target_type": "Designer",
                "method": "rule",
            })

        # 底盘
        for chassis in rule_result["chassis"]:
            global_entities["Chassis"].add(chassis)
            global_relations.append({
                "source": weapon_name,
                "source_type": "Artillery",
                "relation": "USES_CHASSIS",
                "target": chassis,
                "target_type": "Chassis",
                "method": "rule",
            })

        # 弹药
        for ammo in rule_result["ammo"]:
            global_entities["Ammunition"].add(ammo)
            global_relations.append({
                "source": weapon_name,
                "source_type": "Artillery",
                "relation": "USES_AMMO",
                "target": ammo,
                "target_type": "Ammunition",
                "method": "rule",
            })

        # 衍生型号
        for deriv in rule_result["derivatives"]:
            global_entities["Derivative"].add(deriv["name"])
            global_relations.append({
                "source": deriv["name"],
                "source_type": "Derivative",
                "relation": "DERIVED_FROM",
                "target": weapon_name,
                "target_type": "Artillery",
                "method": "rule",
                "description": deriv.get("description", ""),
            })

        # 出口/服役国家
        for country in rule_result["equipped_countries"]:
            global_entities["Country"].add(country)
            global_relations.append({
                "source": weapon_name,
                "source_type": "Artillery",
                "relation": "EQUIPPED_BY",
                "target": country,
                "target_type": "Country",
                "method": "rule",
            })

        # 子类别
        for subtype in rule_result.get("subtypes", []):
            global_entities["SubCategory"].add(subtype)
            global_relations.append({
                "source": weapon_name,
                "source_type": "Artillery",
                "relation": "IS_SUBTYPE_OF",
                "target": subtype,
                "target_type": "SubCategory",
                "method": "rule",
            })

        # 服役军种
        for branch in rule_result.get("branches", []):
            global_entities["MilitaryBranch"].add(branch)
            global_relations.append({
                "source": weapon_name,
                "source_type": "Artillery",
                "relation": "SERVED_IN",
                "target": branch,
                "target_type": "MilitaryBranch",
                "method": "rule",
            })

        # 武器属性作为关系(增加关系数量)
        params = art.get("parameters", {})
        param_label_map = {
            "caliber": "口径",
            "weight": "重量",
            "range": "射程",
            "rate_of_fire": "射速",
            "length": "全长",
            "barrel_length": "炮管长",
            "width": "全宽",
            "height": "全高",
        }
        for param_key, param_value in params.items():
            if param_value:
                label = param_label_map.get(param_key, param_key)
                global_entities["Property"].add(f"{label}={param_value}")
                global_relations.append({
                    "source": weapon_name,
                    "source_type": "Artillery",
                    "relation": "HAS_PROPERTY",
                    "target": f"{label}={param_value}",
                    "target_type": "Property",
                    "method": "rule",
                })

        # --- 合并LLM结果 ---
        if llm_result and isinstance(llm_result, list):
            existing = {(r["relation"], r["target"]) for r in global_relations if r.get("source") == weapon_name}
            for item in llm_result:
                if not isinstance(item, dict):
                    continue
                rel = item.get("relation", "")
                target = item.get("target", "")
                ttype = item.get("target_type", "")
                if (rel, target) in existing or not target:
                    continue
                if ttype in global_entities:
                    global_entities[ttype].add(target)
                global_relations.append({
                    "source": weapon_name if rel != "DERIVED_FROM" else item.get("source", ""),
                    "source_type": "Artillery" if rel != "DERIVED_FROM" else "Derivative",
                    "relation": rel,
                    "target": target if rel != "DERIVED_FROM" else weapon_name,
                    "target_type": ttype,
                    "method": "llm",
                })
                existing.add((rel, target))

        processed += 1
        if processed % 10 == 0:
            print(f"  已处理: {processed}/{len(artillery_data)} (累计关系: {len(global_relations)})")

    # 转为列表
    for etype in global_entities:
        global_entities[etype] = sorted(global_entities[etype])

    print(f"\n深度抽取结果统计:")
    for etype, elist in global_entities.items():
        print(f"  {etype}: {len(elist)}")
    print(f"  关系总数: {len(global_relations)}")

    rel_counts = {}
    for r in global_relations:
        rel_counts[r["relation"]] = rel_counts.get(r["relation"], 0) + 1
    for k, v in sorted(rel_counts.items()):
        print(f"    {k}: {v}")

    method_counts = {"rule": 0, "llm": 0}
    for r in global_relations:
        m = r.get("method", "rule")
        method_counts[m] = method_counts.get(m, 0) + 1
    print(f"  抽取方法: 规则={method_counts['rule']}, LLM={method_counts.get('llm', 0)}")

    # 保存结果
    output = {
        "entities": {k: list(v) if isinstance(v, set) else v for k, v in global_entities.items()},
        "relations": global_relations,
    }

    with open(os.path.join(OUTPUT_DIR, "step3_deep_extract.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n已保存至 data/output/step3_deep_extract.json")
    return output


if __name__ == "__main__":
    main()
