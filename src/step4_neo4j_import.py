# -*- coding: utf-8 -*-
"""
步骤4: Neo4j 知识图谱导入
将step1-3抽取的所有实体和关系导入Neo4j数据库
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

from neo4j import GraphDatabase

OUTPUT_DIR = "../data/output"

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "12345678")


def create_constraints(session):
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Artillery) REQUIRE a.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Country) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Institution) REQUIRE i.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Designer) REQUIRE d.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Ammunition) REQUIRE a.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Derivative) REQUIRE d.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (w:War) REQUIRE w.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chassis) REQUIRE c.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:SubCategory) REQUIRE s.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MilitaryBranch) REQUIRE m.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Property) REQUIRE p.name IS UNIQUE",
    ]
    for c in constraints:
        try:
            session.run(c)
        except Exception as e:
            print(f"  约束创建跳过: {e}")


def import_countries(session, countries):
    for name in countries:
        session.run("MERGE (c:Country {name: $name})", name=name)
    print(f"  导入Country: {len(countries)}")


def import_categories(session, categories):
    for name in categories:
        session.run("MERGE (c:Category {name: $name})", name=name)
    print(f"  导入Category: {len(categories)}")


def import_artillery(session, artillery_list, image_map):
    count = 0
    for art in artillery_list:
        params = art.get("parameters", {})
        image_path = image_map.get(art["name"], "")

        session.run("""
            MERGE (a:Artillery {name: $name})
            SET a.caliber = $caliber,
                a.model = $model,
                a.core_model = $core_model,
                a.subtype = $subtype,
                a.weight = $weight,
                a.range = $range,
                a.rate_of_fire = $rate_of_fire,
                a.length = $length,
                a.barrel_length = $barrel_length,
                a.width = $width,
                a.height = $height,
                a.image_path = $image_path,
                a.page = $page
        """,
            name=art["name"],
            caliber=art.get("caliber", ""),
            model=art.get("model", ""),
            core_model=art.get("core_model", ""),
            subtype=art.get("subtype", ""),
            weight=params.get("weight", ""),
            range=params.get("range", ""),
            rate_of_fire=params.get("rate_of_fire", ""),
            length=params.get("length", ""),
            barrel_length=params.get("barrel_length", ""),
            width=params.get("width", ""),
            height=params.get("height", ""),
            image_path=image_path,
            page=art.get("page", 0),
        )
        count += 1
    print(f"  导入Artillery: {count}")


def import_deep_entities(session, entities):
    label_map = {
        "Institution": "Institution",
        "Designer": "Designer",
        "Ammunition": "Ammunition",
        "Derivative": "Derivative",
        "War": "War",
        "Chassis": "Chassis",
        "SubCategory": "SubCategory",
        "MilitaryBranch": "MilitaryBranch",
        "Property": "Property",
        "Country": "Country",
    }
    for etype, elist in entities.items():
        label = label_map.get(etype, etype)
        if not elist:
            continue
        for name in elist:
            session.run(f"MERGE (n:{label} {{name: $name}})", name=name)
        print(f"  导入{label}: {len(elist)}")


def import_relations(session, relations_step1, relations_step3):
    all_relations = relations_step1 + relations_step3

    # 动态生成Cypher: 根据source_type和target_type匹配节点
    def get_cypher(rel_type, source_type, target_type):
        return f"""
            MATCH (a:{source_type} {{name: $source}})
            MATCH (b:{target_type} {{name: $target}})
            MERGE (a)-[:`{rel_type}`]->(b)
        """

    success = 0
    failed = 0
    failed_examples = []
    for rel in all_relations:
        rel_type = rel.get("relation", "")
        source = rel.get("source", "")
        target = rel.get("target", "")
        source_type = rel.get("source_type", "")
        target_type = rel.get("target_type", "")

        if not source or not target or not rel_type:
            failed += 1
            continue

        cypher = get_cypher(rel_type, source_type, target_type)

        try:
            session.run(cypher, source=source, target=target)
            success += 1
        except Exception as e:
            failed += 1
            if len(failed_examples) < 5:
                failed_examples.append(f"{source}-[{rel_type}]->{target}: {e}")

    print(f"  导入关系: 成功={success}, 失败={failed}")
    if failed_examples:
        print("  失败示例:")
        for ex in failed_examples:
            print(f"    {ex}")


def main():
    print("=" * 60)
    print("步骤4: Neo4j 知识图谱导入")
    print("=" * 60)

    # 加载数据
    with open(os.path.join(OUTPUT_DIR, "step2_ocr_extract.json"), "r", encoding="utf-8") as f:
        step2_data = json.load(f)

    raw_step3_path = os.path.join(OUTPUT_DIR, "step3_deep_extract.json")
    step3_path = raw_step3_path if os.path.exists(raw_step3_path) else os.path.join(OUTPUT_DIR, "step3_clean_extract.json")
    if os.path.exists(step3_path):
        with open(step3_path, "r", encoding="utf-8") as f:
            step3_data = json.load(f)
        print(f"  深度关系来源: {os.path.basename(step3_path)}")
    else:
        print("[WARN] step3数据不存在,仅导入step1-2数据")
        step3_data = {"entities": {}, "relations": []}

    # 合并step3的Country到step2
    if "Country" in step3_data.get("entities", {}):
        step2_countries = set(step2_data.get("countries", []))
        step2_countries.update(step3_data["entities"]["Country"])
        step2_data["countries"] = sorted(step2_countries)

    # 连接Neo4j
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("  Neo4j连接成功")
    except Exception as e:
        print(f"[ERROR] Neo4j连接失败: {e}")
        print("  请确保Neo4j服务已启动,并检查连接配置")
        print("  默认配置: bolt://localhost:7687, 用户neo4j, 密码12345678")
        print("  可通过环境变量 NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD 修改")
        return

    with driver.session(database="neo4j") as session:
        print("\n[1/5] 清空旧数据...")
        session.run("MATCH (n) DETACH DELETE n")
        print("  已清空")

        print("\n[2/5] 创建唯一性约束...")
        create_constraints(session)

        print("\n[3/5] 导入基础实体...")
        import_countries(session, step2_data["countries"])
        import_categories(session, step2_data["categories"])
        import_artillery(session, step2_data["artillery"], step2_data.get("image_map", {}))

        print("\n[4/5] 导入深度抽取实体...")
        import_deep_entities(session, step3_data.get("entities", {}))

        print("\n[5/5] 导入关系...")
        import_relations(session, step2_data["relations"], step3_data.get("relations", []))

    driver.close()

    # 统计最终图谱规模
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session(database="neo4j") as session:
        node_result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt")
        print("\n最终图谱统计:")
        total_nodes = 0
        for record in node_result:
            print(f"  {record['label']}: {record['cnt']}")
            total_nodes += record['cnt']
        print(f"  节点总数: {total_nodes}")

        rel_result = session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS cnt")
        total_rels = 0
        for record in rel_result:
            print(f"  {record['type']}: {record['cnt']}")
            total_rels += record['cnt']
        print(f"  关系总数: {total_rels}")

    driver.close()
    print("\n导入完成!")


if __name__ == "__main__":
    main()
