from __future__ import annotations

import json
from math import exp
from pathlib import Path

import pandas as pd


ROOT = Path("/Users/lyh/Desktop/competiton")
MODEL_DIR = ROOT / "outputs" / "model_results"
FEATURE_FILE = MODEL_DIR / "white_list_feature_matrix.csv"
LABEL_FILE = ROOT / "outputs" / "low_altitude_pipeline" / "企业主表.csv"
PRED_FILE = MODEL_DIR / "white_list_predictions.csv"
REPORT_FILE = MODEL_DIR / "white_list_model_report.json"


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def sigmoid(x: float) -> float:
    if x >= 0:
        z = exp(-x)
        return 1.0 / (1.0 + z)
    z = exp(x)
    return z / (1.0 + z)


def logistic_predict(matrix: pd.DataFrame, weights: pd.Series, intercept: float) -> pd.Series:
    aligned = matrix.reindex(columns=weights.index, fill_value=0.0)
    scores = aligned @ weights + intercept
    return scores.map(sigmoid)


def standardize(train: pd.DataFrame, valid: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    mean = train.mean(axis=0)
    std = train.std(axis=0).replace(0, 1.0)
    return (train - mean) / std, (valid - mean) / std, mean, std


def fit_logit(x: pd.DataFrame, y: pd.Series, steps: int = 2000, lr: float = 0.05, l2: float = 0.05) -> tuple[pd.Series, float]:
    x = x.copy()
    x.insert(0, "__intercept__", 1.0)
    w = pd.Series(0.0, index=x.columns, dtype=float)
    y = y.astype(float)

    for _ in range(steps):
        scores = x @ w
        preds = scores.map(sigmoid)
        error = y - preds
        grad = (x.mul(error, axis=0)).mean(axis=0)
        grad.loc[w.index.difference(["__intercept__"])] -= l2 * w.loc[w.index.difference(["__intercept__"])]
        w = w + lr * grad

    return w.drop("__intercept__"), float(w["__intercept__"])


def auc_score(y_true: pd.Series, y_score: pd.Series) -> float:
    frame = pd.DataFrame({"y": y_true.astype(int), "s": y_score.astype(float)}).sort_values("s")
    pos = int((frame["y"] == 1).sum())
    neg = int((frame["y"] == 0).sum())
    if pos == 0 or neg == 0:
        return 0.0
    rank = pd.Series(range(1, len(frame) + 1), index=frame.index)
    sum_pos = float(rank.loc[frame["y"] == 1].sum())
    return float((sum_pos - pos * (pos + 1) / 2) / (pos * neg))


def split_holdout(df: pd.DataFrame, y: pd.Series) -> tuple[pd.Index, pd.Index]:
    pos_idx = df.index[y == 1].tolist()
    neg_idx = df.index[y == 0].tolist()
    pos_holdout = pos_idx[-max(1, len(pos_idx) // 4):]
    neg_holdout = neg_idx[-max(1, len(neg_idx) // 4):]
    valid_idx = pd.Index(sorted(set(pos_holdout + neg_holdout)))
    train_idx = df.index.difference(valid_idx)
    return train_idx, valid_idx


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(FEATURE_FILE)
    label_df = pd.read_csv(LABEL_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    label_df["统一社会信用代码"] = label_df["统一社会信用代码"].map(clean_text)
    label_df["样本标记"] = label_df["样本标记"].map(clean_text)
    label_map = label_df.set_index("统一社会信用代码")["样本标记"].to_dict()
    df["样本标记"] = df["统一社会信用代码"].map(label_map).fillna("")
    y = (df["样本标记"] == "是").astype(int)

    ignore = {"统一社会信用代码", "公司名称", "企业标准名", "样本标记"}
    x = df.drop(columns=[col for col in ignore if col in df.columns], errors="ignore")
    x = x.select_dtypes(include=["number"]).fillna(0.0)

    if x.empty:
        raise RuntimeError("No numeric features found in feature matrix.")

    train_idx, valid_idx = split_holdout(df, y)
    x_train, x_valid = x.loc[train_idx], x.loc[valid_idx]
    y_train, y_valid = y.loc[train_idx], y.loc[valid_idx]

    x_train_s, x_valid_s, mean, std = standardize(x_train, x_valid)
    weights, intercept = fit_logit(x_train_s, y_train)
    train_proba = logistic_predict(x_train_s, weights, intercept)
    valid_proba = logistic_predict(x_valid_s, weights, intercept)
    all_proba = logistic_predict(((x - mean) / std).fillna(0.0), weights, intercept)

    train_pred = (train_proba >= 0.5).astype(int)
    valid_pred = (valid_proba >= 0.5).astype(int)

    def metrics(y_true: pd.Series, pred: pd.Series, proba: pd.Series) -> dict[str, float]:
        tp = int(((pred == 1) & (y_true == 1)).sum())
        fp = int(((pred == 1) & (y_true == 0)).sum())
        fn = int(((pred == 0) & (y_true == 1)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        acc = float((pred == y_true).mean())
        auc = auc_score(y_true, proba)
        return {"accuracy": acc, "precision": precision, "recall": recall, "f1": f1, "auc": auc}

    report = {
        "rows": int(len(df)),
        "train_rows": int(len(train_idx)),
        "valid_rows": int(len(valid_idx)),
        "train_metrics": metrics(y_train, train_pred, train_proba),
        "valid_metrics": metrics(y_valid, valid_pred, valid_proba),
        "top_coefficients": weights.abs().sort_values(ascending=False).head(20).to_dict(),
    }

    out = df[["统一社会信用代码", "公司名称", "企业标准名", "样本标记"]].copy()
    out["predicted_probability"] = all_proba.round(6)
    out["predicted_label"] = (out["predicted_probability"] >= 0.5).map({True: "是", False: "否"})
    out["true_label"] = out["样本标记"]
    out = out.sort_values(by="predicted_probability", ascending=False)
    out.to_csv(PRED_FILE, index=False, encoding="utf-8-sig")

    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Predictions saved to: {PRED_FILE}")
    print(f"Report saved to: {REPORT_FILE}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
