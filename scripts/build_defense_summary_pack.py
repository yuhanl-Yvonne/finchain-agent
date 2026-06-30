from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path("/Users/lyh/Desktop/competiton")
GRAPH_DIR = ROOT / "outputs" / "graphsage"
MODEL_DIR = ROOT / "outputs" / "model_results"
DELIVER_DIR = ROOT / "outputs" / "final_delivery"

GRAPH_REPORT = GRAPH_DIR / "graphsage_report.json"
GRAPH_TOP20 = GRAPH_DIR / "top20_graphsage_recommendations.csv"
LR_TOP20 = MODEL_DIR / "top20_whitelist_recommendations.csv"

SUMMARY_MD = DELIVER_DIR / "答辩汇报版结果说明.md"
FINAL_TOP_CSV = DELIVER_DIR / "最终推荐简表.csv"
FINAL_TOP_XLSX = DELIVER_DIR / "最终推荐简表.xlsx"


def main() -> None:
    DELIVER_DIR.mkdir(parents=True, exist_ok=True)

    report = json.loads(GRAPH_REPORT.read_text(encoding="utf-8"))
    graph_top = pd.read_csv(GRAPH_TOP20, encoding="utf-8-sig")
    lr_top = pd.read_csv(LR_TOP20, encoding="utf-8-sig")

    intersection = sorted(set(graph_top["公司名称"]) & set(lr_top["公司名称"]))

    final_top = graph_top[
        [
            "推荐顺位",
            "公司名称",
            "统一社会信用代码",
            "模型推荐分数",
            "所属城市",
            "产业链环节",
            "企业类型标签",
            "推荐理由",
            "建议动作",
        ]
    ].copy()
    final_top.to_csv(FINAL_TOP_CSV, index=False, encoding="utf-8-sig")
    final_top.to_excel(FINAL_TOP_XLSX, index=False)

    top10_lines = []
    for _, row in graph_top.head(10).iterrows():
        top10_lines.append(
            f"{int(row['推荐顺位'])}. {row['公司名称']}（{row['所属城市']}，{row['产业链环节']}，分数 {float(row['模型推荐分数']):.6f}）"
        )

    summary = f"""# 答辩汇报版结果说明

## 一、图谱与模型整体方案
- 本项目先构建低空经济知识图谱，将企业节点与产业链环节、区域、风险事件、专利信息关联起来。
- 在此基础上，进一步构建 `Company-Company` 同构图，连边规则为“同城 + 同产业链环节”。
- 节点特征使用已去标签泄漏的企业画像特征矩阵，监督目标为 `企业主表.csv` 中的 `样本标记`。
- 模型采用两层 GraphSAGE，在 CPU 环境完成训练，并将预测分数与 embedding 回写至 Neo4j。

## 二、GraphSAGE训练结果
- 节点数：{report['num_nodes']}
- 边数：{report['num_edges']}
- 正样本数：{report['positive_labels']}
- 最优轮次：{report['best_epoch']}
- 验证集 F1：{report['val_metrics']['f1']:.4f}
- 验证集 AUC：{report['val_metrics']['auc']:.4f}
- 测试集 F1：{report['test_metrics']['f1']:.4f}
- 测试集 AUC：{report['test_metrics']['auc']:.4f}

## 三、模型结果特征
- GraphSAGE Top20 推荐名单已生成，并写回 Neo4j 的 `Company` 节点属性。
- GraphSAGE Top20 与原逻辑回归 Top20 的交集为 {len(intersection)} 家，说明两种方法对核心头部企业判断高度一致，但排序存在差异。
- 交集企业包括：{", ".join(intersection[:10])}。

## 四、GraphSAGE Top10 推荐企业
{chr(10).join('- ' + line for line in top10_lines)}

## 五、最终使用建议
- 以 `top20_graphsage_recommendations.csv` 为模型推荐底表。
- 结合 `neo4j验图查询清单.md` 在 Browser 中逐条核验企业的产业链位置、区域归属与风险事件。
- 在 `最终白名单人工核验表.xlsx` 中补充人工判断，形成最终白名单名单。
- 建议最终汇报时突出“图谱构建 + 图神经网络排序 + 人工核验闭环”三步法。
"""

    SUMMARY_MD.write_text(summary, encoding="utf-8")

    print(f"Saved summary markdown to: {SUMMARY_MD}")
    print(f"Saved final top csv to: {FINAL_TOP_CSV}")
    print(f"Saved final top xlsx to: {FINAL_TOP_XLSX}")


if __name__ == "__main__":
    main()
