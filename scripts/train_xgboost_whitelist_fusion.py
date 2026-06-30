from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from xgboost import XGBClassifier


ROOT = Path("/Users/lyh/Desktop/competiton")
MODEL_DIR = ROOT / "outputs" / "model_results"
GRAPH_DIR = ROOT / "outputs" / "graphsage"
LOW_ALTITUDE_DIR = ROOT / "outputs" / "low_altitude_pipeline"

FEATURE_FILE = MODEL_DIR / "white_list_feature_matrix.csv"
EMBED_FILE = GRAPH_DIR / "graphsage_embeddings.csv"
GRAPH_PRED_FILE = GRAPH_DIR / "graphsage_predictions.csv"
LABEL_FILE = LOW_ALTITUDE_DIR / "企业主表.csv"

PRED_FILE = MODEL_DIR / "xgboost_fusion_predictions.csv"
REPORT_FILE = MODEL_DIR / "xgboost_fusion_report.json"
IMPORTANCE_FILE = MODEL_DIR / "xgboost_fusion_feature_importance.csv"
TOP20_FILE = MODEL_DIR / "top20_xgboost_fusion_recommendations.csv"
MODEL_FILE = MODEL_DIR / "xgboost_fusion_model.json"
SHAP_VALUES_FILE = MODEL_DIR / "xgboost_fusion_shap_values.csv"
SHAP_SUMMARY_FILE = MODEL_DIR / "xgboost_fusion_shap_summary.csv"

SEED = 42


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def normalize_uscc(value: object) -> str:
    text = clean_text(value).upper().replace(" ", "")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def to_number(value: object) -> float:
    text = clean_text(value).replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def auc_score(y_true: pd.Series, y_score: pd.Series) -> float:
    frame = pd.DataFrame({"y": y_true.astype(int), "s": y_score.astype(float)}).sort_values("s")
    pos = int((frame["y"] == 1).sum())
    neg = int((frame["y"] == 0).sum())
    if pos == 0 or neg == 0:
        return 0.0
    rank = pd.Series(range(1, len(frame) + 1), index=frame.index)
    sum_pos = float(rank.loc[frame["y"] == 1].sum())
    return float((sum_pos - pos * (pos + 1) / 2) / (pos * neg))


def classification_metrics(y_true: pd.Series, y_pred: pd.Series, y_prob: pd.Series) -> dict[str, float]:
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / max(1, len(y_true))
    auc = auc_score(y_true, y_prob)
    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auc": float(auc),
    }


def build_reason(row: pd.Series) -> str:
    parts: list[str] = []
    if row.get("graphsage_score", 0.0) >= 0.9:
        parts.append("图嵌入相似性强")
    elif row.get("graphsage_score", 0.0) >= 0.7:
        parts.append("图结构关联度较高")

    city = clean_text(row.get("所属城市"))
    if city:
        parts.append(f"位于{city}重点区域")

    chain = clean_text(row.get("产业链环节"))
    if chain:
        parts.append(f"处于{chain}环节")

    ty_score = to_number(row.get("天眼评分"))
    if ty_score >= 80:
        parts.append("企业综合活跃度高")
    elif ty_score >= 70:
        parts.append("企业综合基础较好")

    staff = to_number(row.get("参保人数"))
    if staff >= 300:
        parts.append(f"参保规模较大({int(staff)}人)")
    elif staff >= 50:
        parts.append(f"具备一定团队规模({int(staff)}人)")

    patent_count = to_number(row.get("graph_patent_degree"))
    if patent_count >= 20:
        parts.append("图谱专利关联较强")

    return "；".join(parts[:4]) or "融合模型综合得分较高，建议优先核验"


def pretty_feature_name(feature: str) -> str:
    if feature.startswith("emb_"):
        return f"图嵌入特征{feature}"
    aliases = {
        "企业年龄": "企业年龄",
        "注册资本数值": "注册资本",
        "实缴资本数值": "实缴资本",
        "参保人数数值": "参保人数",
        "天眼评分数值": "天眼评分",
        "经营范围长度": "经营范围长度",
        "地址长度": "地址长度",
        "panel_patent_growth": "专利增长",
        "panel_patent_avg": "专利平均活跃度",
        "panel_patent_trend_slope": "专利趋势斜率",
    }
    return aliases.get(feature, feature)


def summarize_shap_row(row: pd.Series, positive: bool, top_n: int = 3) -> str:
    filtered = row[row > 0] if positive else row[row < 0]
    if filtered.empty:
        return "无明显正向因子" if positive else "无明显负向因子"
    ranked = filtered.sort_values(ascending=not positive).head(top_n)
    pieces = [f"{pretty_feature_name(name)}({value:.3f})" for name, value in ranked.items()]
    return "；".join(pieces)


def build_risk_hint(row: pd.Series) -> str:
    hints: list[str] = []
    risk_count = to_number(row.get("graph_risk_event_count"))
    if risk_count >= 5:
        hints.append(f"风险事件较多({int(risk_count)}条)")
    elif risk_count >= 1:
        hints.append(f"存在风险事件({int(risk_count)}条)")

    status = clean_text(row.get("登记状态"))
    if status and status not in {"存续", "在业", "开业"}:
        hints.append(f"登记状态需关注({status})")

    if not clean_text(row.get("官网")):
        hints.append("官网信息缺失")

    return "；".join(hints) if hints else "未见显著高风险信号，仍需人工复核"


def build_level(score: float) -> str:
    if score >= 0.9:
        return "A"
    if score >= 0.75:
        return "B"
    if score >= 0.55:
        return "C"
    return "D"


def stratified_split(df: pd.DataFrame, label_col: str) -> tuple[pd.Index, pd.Index, pd.Index]:
    train_idx: list[int] = []
    val_idx: list[int] = []
    test_idx: list[int] = []

    for _, group in df.groupby(label_col):
        group = group.sample(frac=1.0, random_state=SEED)
        n = len(group)
        n_train = max(1, int(round(n * 0.7)))
        n_val = max(1, int(round(n * 0.15)))
        if n_train + n_val >= n:
            n_val = max(1, n - n_train - 1)
        n_test = n - n_train - n_val
        if n_test <= 0:
            n_test = 1
            if n_train > n_val:
                n_train -= 1
            else:
                n_val -= 1

        idx = group.index.tolist()
        train_idx.extend(idx[:n_train])
        val_idx.extend(idx[n_train:n_train + n_val])
        test_idx.extend(idx[n_train + n_val:])

    return pd.Index(sorted(train_idx)), pd.Index(sorted(val_idx)), pd.Index(sorted(test_idx))


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    feat = pd.read_csv(FEATURE_FILE, encoding="utf-8-sig")
    embed = pd.read_csv(EMBED_FILE, encoding="utf-8-sig")
    graph_pred = pd.read_csv(GRAPH_PRED_FILE, encoding="utf-8-sig")
    label_df = pd.read_csv(LABEL_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    feat["统一社会信用代码"] = feat["统一社会信用代码"].map(normalize_uscc)
    embed["company_id"] = embed["company_id"].map(normalize_uscc)
    graph_pred["company_id"] = graph_pred["company_id"].map(normalize_uscc)
    label_df["统一社会信用代码"] = label_df["统一社会信用代码"].map(normalize_uscc)
    label_df["样本标记"] = label_df["样本标记"].map(clean_text)

    graph_pred["pred_prob"] = pd.to_numeric(graph_pred["pred_prob"], errors="coerce").fillna(0.0)
    graph_pred["pred_label"] = graph_pred["pred_label"].map(clean_text)

    model_df = feat.merge(embed, left_on="统一社会信用代码", right_on="company_id", how="left")
    model_df = model_df.merge(
        graph_pred[["company_id", "pred_prob", "pred_label"]],
        on="company_id",
        how="left",
    )
    model_df["graphsage_score"] = model_df["pred_prob"].fillna(0.0)
    model_df["graphsage_pred_label"] = model_df["pred_label"].fillna("")
    model_df = model_df.drop(columns=["company_id", "pred_prob", "pred_label"], errors="ignore")
    model_df["样本标记"] = model_df["统一社会信用代码"].map(label_df.set_index("统一社会信用代码")["样本标记"]).fillna("")
    model_df["label"] = (model_df["样本标记"] == "是").astype(int)

    text_columns = {"统一社会信用代码", "公司名称", "企业标准名", "样本标记"}
    leakage_columns = {
        "label",
        "graphsage_pred_label",
        "graphsage_score",
        "成立年份",
    }
    numeric_df = model_df.drop(
        columns=[col for col in text_columns | leakage_columns if col in model_df.columns],
        errors="ignore",
    )
    numeric_df = numeric_df.select_dtypes(include=["number"]).fillna(0.0)

    if numeric_df.empty:
        raise RuntimeError("No numeric features available for XGBoost fusion training.")

    train_idx, val_idx, test_idx = stratified_split(model_df, "label")
    x_train = numeric_df.loc[train_idx]
    y_train = model_df.loc[train_idx, "label"]
    x_val = numeric_df.loc[val_idx]
    y_val = model_df.loc[val_idx, "label"]
    x_test = numeric_df.loc[test_idx]
    y_test = model_df.loc[test_idx, "label"]

    pos = max(1, int((y_train == 1).sum()))
    neg = max(1, int((y_train == 0).sum()))
    scale_pos_weight = neg / pos

    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        min_child_weight=2,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=SEED,
        scale_pos_weight=scale_pos_weight,
    )
    model.fit(x_train, y_train)
    model.save_model(MODEL_FILE)

    train_prob = pd.Series(model.predict_proba(x_train)[:, 1], index=train_idx)
    val_prob = pd.Series(model.predict_proba(x_val)[:, 1], index=val_idx)
    test_prob = pd.Series(model.predict_proba(x_test)[:, 1], index=test_idx)
    all_prob = pd.Series(model.predict_proba(numeric_df)[:, 1], index=model_df.index)

    train_pred = (train_prob >= 0.5).astype(int)
    val_pred = (val_prob >= 0.5).astype(int)
    test_pred = (test_prob >= 0.5).astype(int)
    all_pred = (all_prob >= 0.5).astype(int)

    pred_df = model_df[["统一社会信用代码", "公司名称", "企业标准名", "样本标记", "graphsage_score", "graphsage_pred_label"]].copy()
    pred_df["xgb_fusion_score"] = all_prob.round(6)
    pred_df["xgb_fusion_pred_label"] = all_pred.map({1: "是", 0: "否"})
    pred_df["white_list_level"] = pred_df["xgb_fusion_score"].map(build_level)
    pred_df["true_label"] = pred_df["样本标记"]

    booster = model.get_booster()
    dmatrix = xgb.DMatrix(numeric_df, feature_names=numeric_df.columns.tolist())
    shap_raw = booster.predict(dmatrix, pred_contribs=True)
    shap_feature_names = numeric_df.columns.tolist() + ["bias"]
    shap_df = pd.DataFrame(shap_raw, columns=shap_feature_names, index=model_df.index)

    shap_values_only = shap_df[numeric_df.columns.tolist()].copy()
    shap_export = pd.concat(
        [
            model_df[["统一社会信用代码", "公司名称"]],
            shap_values_only.reset_index(drop=True),
        ],
        axis=1,
    )
    shap_export.to_csv(SHAP_VALUES_FILE, index=False, encoding="utf-8-sig")

    shap_summary = pd.DataFrame(
        {
            "feature": numeric_df.columns,
            "mean_abs_shap": shap_values_only.abs().mean(axis=0).values,
            "mean_shap": shap_values_only.mean(axis=0).values,
        }
    ).sort_values("mean_abs_shap", ascending=False)
    shap_summary.to_csv(SHAP_SUMMARY_FILE, index=False, encoding="utf-8-sig")

    pred_df["shap_top_positive"] = shap_values_only.apply(lambda row: summarize_shap_row(row, positive=True), axis=1)
    pred_df["shap_top_negative"] = shap_values_only.apply(lambda row: summarize_shap_row(row, positive=False), axis=1)
    pred_df = pred_df.sort_values("xgb_fusion_score", ascending=False)
    pred_df.to_csv(PRED_FILE, index=False, encoding="utf-8-sig")

    importance = pd.DataFrame(
        {
            "feature": numeric_df.columns,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)
    importance.to_csv(IMPORTANCE_FILE, index=False, encoding="utf-8-sig")

    report = {
        "rows": int(len(model_df)),
        "positive_labels": int(model_df["label"].sum()),
        "negative_labels": int((model_df["label"] == 0).sum()),
        "train_rows": int(len(train_idx)),
        "val_rows": int(len(val_idx)),
        "test_rows": int(len(test_idx)),
        "config": {
            "n_estimators": 300,
            "max_depth": 4,
            "learning_rate": 0.05,
            "subsample": 0.9,
            "colsample_bytree": 0.8,
            "min_child_weight": 2,
            "scale_pos_weight": float(scale_pos_weight),
            "seed": SEED,
        },
        "train_metrics": classification_metrics(y_train, train_pred, train_prob),
        "val_metrics": classification_metrics(y_val, val_pred, val_prob),
        "test_metrics": classification_metrics(y_test, test_pred, test_prob),
        "top_features": importance.head(30).to_dict(orient="records"),
        "top_shap_features": shap_summary.head(30).to_dict(orient="records"),
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    base_cols = [
        "统一社会信用代码",
        "公司名称",
        "所属城市",
        "所属区县",
        "企业类型标签",
        "产业链环节",
        "产业链判定依据",
        "企业规模",
        "参保人数",
        "注册资本",
        "天眼评分",
        "登记状态",
        "官网",
        "经营范围",
    ]
    base = label_df[base_cols].drop_duplicates(subset=["统一社会信用代码"])
    graph_cols = [
        col
        for col in ["统一社会信用代码", "graph_chain_degree", "graph_region_degree", "graph_risk_event_count", "graph_patent_degree"]
        if col in feat.columns
    ]
    graph_stats = feat[graph_cols].drop_duplicates(subset=["统一社会信用代码"]) if graph_cols else feat[["统一社会信用代码"]].copy()
    for col in ["graph_chain_degree", "graph_region_degree", "graph_risk_event_count", "graph_patent_degree"]:
        if col not in graph_stats.columns:
            graph_stats[col] = 0

    top20 = pred_df.head(20).merge(base, on=["统一社会信用代码", "公司名称"], how="left").merge(
        graph_stats, on="统一社会信用代码", how="left"
    )
    top20["推荐顺位"] = range(1, len(top20) + 1)
    top20["推荐理由"] = top20.apply(build_reason, axis=1)
    top20["风险提示"] = top20.apply(build_risk_hint, axis=1)
    top20["SHAP正向解释"] = top20["shap_top_positive"]
    top20["SHAP负向解释"] = top20["shap_top_negative"]
    top20["建议动作"] = top20["white_list_level"].map(
        {
            "A": "优先纳入白名单候选并立即人工核验",
            "B": "纳入白名单候选并重点核验",
            "C": "作为储备候选继续补充证据",
            "D": "暂不优先推荐",
        }
    )
    top20 = top20[
        [
            "推荐顺位",
            "统一社会信用代码",
            "公司名称",
            "xgb_fusion_score",
            "white_list_level",
            "xgb_fusion_pred_label",
            "true_label",
            "graphsage_score",
            "graphsage_pred_label",
            "所属城市",
            "所属区县",
            "企业类型标签",
            "产业链环节",
            "企业规模",
            "参保人数",
            "注册资本",
            "天眼评分",
            "graph_chain_degree",
            "graph_region_degree",
            "graph_risk_event_count",
            "graph_patent_degree",
            "推荐理由",
            "SHAP正向解释",
            "SHAP负向解释",
            "风险提示",
            "建议动作",
            "产业链判定依据",
            "经营范围",
        ]
    ].rename(
        columns={
            "xgb_fusion_score": "融合白名单分数",
            "white_list_level": "白名单等级",
            "xgb_fusion_pred_label": "融合预测标签",
            "true_label": "当前样本标签",
            "graphsage_score": "GraphSAGE分数",
            "graphsage_pred_label": "GraphSAGE预测标签",
            "graph_chain_degree": "图谱产业链连接数",
            "graph_region_degree": "图谱区域连接数",
            "graph_risk_event_count": "图谱风险事件数",
            "graph_patent_degree": "图谱专利连接数",
        }
    )
    top20.to_csv(TOP20_FILE, index=False, encoding="utf-8-sig")

    print(f"Saved predictions to: {PRED_FILE}")
    print(f"Saved report to: {REPORT_FILE}")
    print(f"Saved feature importance to: {IMPORTANCE_FILE}")
    print(f"Saved model to: {MODEL_FILE}")
    print(f"Saved SHAP values to: {SHAP_VALUES_FILE}")
    print(f"Saved SHAP summary to: {SHAP_SUMMARY_FILE}")
    print(f"Saved top20 recommendations to: {TOP20_FILE}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
