from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from torch import nn
from torch_geometric.data import Data
from torch_geometric.nn import SAGEConv


ROOT = Path("/Users/lyh/Desktop/competiton")
GRAPH_DIR = ROOT / "outputs" / "graphsage"
LOW_ALTITUDE_DIR = ROOT / "outputs" / "low_altitude_pipeline"

NODES_FILE = GRAPH_DIR / "company_nodes.csv"
FEATURES_FILE = GRAPH_DIR / "company_features.csv"
EDGES_FILE = GRAPH_DIR / "company_edges.csv"
BASE_FILE = LOW_ALTITUDE_DIR / "企业主表.csv"

PRED_FILE = GRAPH_DIR / "graphsage_predictions.csv"
EMBED_FILE = GRAPH_DIR / "graphsage_embeddings.csv"
REPORT_FILE = GRAPH_DIR / "graphsage_report.json"
MODEL_FILE = GRAPH_DIR / "graphsage_model.pt"
TOP20_FILE = GRAPH_DIR / "top20_graphsage_recommendations.csv"

SEED = 42
HIDDEN_DIM = 64
DROPOUT = 0.2
LR = 0.01
WEIGHT_DECAY = 5e-4
EPOCHS = 200
PATIENCE = 20


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def make_data() -> tuple[Data, pd.DataFrame, pd.DataFrame]:
    nodes = pd.read_csv(NODES_FILE, encoding="utf-8-sig")
    features = pd.read_csv(FEATURES_FILE, encoding="utf-8-sig")
    edges = pd.read_csv(EDGES_FILE, encoding="utf-8-sig")

    x = torch.tensor(features.drop(columns=["node_index"]).to_numpy(dtype=np.float32), dtype=torch.float32)
    y = torch.tensor(nodes["label"].to_numpy(dtype=np.int64), dtype=torch.long)

    undirected_edges = []
    for _, row in edges.iterrows():
        undirected_edges.append((int(row["src"]), int(row["dst"])))
        undirected_edges.append((int(row["dst"]), int(row["src"])))
    edge_index = torch.tensor(np.array(undirected_edges).T, dtype=torch.long)

    data = Data(
        x=x,
        edge_index=edge_index,
        y=y,
        train_mask=torch.tensor(nodes["train_mask"].to_numpy(dtype=bool)),
        val_mask=torch.tensor(nodes["val_mask"].to_numpy(dtype=bool)),
        test_mask=torch.tensor(nodes["test_mask"].to_numpy(dtype=bool)),
    )
    return data, nodes, edges


class GraphSAGE(nn.Module):
    def __init__(self, in_channels: int, hidden_channels: int, out_channels: int, dropout: float) -> None:
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden_channels)
        self.conv2 = SAGEConv(hidden_channels, out_channels)
        self.dropout = dropout

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        x = self.conv1(x, edge_index)
        x = F.relu(x)
        embedding = F.dropout(x, p=self.dropout, training=self.training)
        logits = self.conv2(embedding, edge_index)
        return logits, x


def metric_frame(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    accuracy = (tp + tn) / max(1, len(y_true))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    pos = int((y_true == 1).sum())
    neg = int((y_true == 0).sum())
    if pos == 0 or neg == 0:
        auc = 0.0
    else:
        order = np.argsort(y_prob)
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.arange(1, len(y_prob) + 1)
        sum_pos = ranks[y_true == 1].sum()
        auc = float((sum_pos - pos * (pos + 1) / 2) / (pos * neg))

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auc": float(auc),
    }


def evaluate(model: GraphSAGE, data: Data, mask: torch.Tensor) -> tuple[float, dict[str, float], torch.Tensor, torch.Tensor]:
    model.eval()
    with torch.no_grad():
        logits, embeddings = model(data.x, data.edge_index)
        loss = F.cross_entropy(logits[mask], data.y[mask]).item()
        prob = torch.softmax(logits, dim=1)[:, 1]
        pred = logits.argmax(dim=1)
        metrics = metric_frame(
            data.y[mask].cpu().numpy(),
            pred[mask].cpu().numpy(),
            prob[mask].cpu().numpy(),
        )
    return loss, metrics, prob, embeddings


def build_top20(pred: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    merged = pred.merge(
        base[
            [
                "统一社会信用代码",
                "公司名称",
                "所属城市",
                "所属区县",
                "企业类型标签",
                "产业链环节",
                "产业链判定依据",
                "天眼评分",
                "企业规模",
                "参保人数",
                "注册资本",
                "经营范围",
            ]
        ],
        left_on=["company_id", "company_name"],
        right_on=["统一社会信用代码", "公司名称"],
        how="left",
    ).sort_values("pred_prob", ascending=False).head(20).copy()
    merged["推荐顺位"] = range(1, len(merged) + 1)
    merged["建议动作"] = "纳入GraphSAGE候选白名单并进入图谱人工核验"
    merged["推荐理由"] = merged.apply(
        lambda row: f"GraphSAGE评分高；位于{clean_text(row.get('所属城市')) or '重点区域'}；处于{clean_text(row.get('产业链环节')) or '相关'}环节；适合优先核验",
        axis=1,
    )
    return merged[
        [
            "推荐顺位",
            "company_id",
            "company_name",
            "pred_prob",
            "pred_label",
            "true_label",
            "所属城市",
            "所属区县",
            "企业类型标签",
            "产业链环节",
            "天眼评分",
            "企业规模",
            "参保人数",
            "注册资本",
            "推荐理由",
            "建议动作",
            "产业链判定依据",
            "经营范围",
        ]
    ].rename(
        columns={
            "company_id": "统一社会信用代码",
            "company_name": "公司名称",
            "pred_prob": "模型推荐分数",
            "pred_label": "模型预测标签",
            "true_label": "当前样本标签",
        }
    )


def main() -> None:
    set_seed(SEED)
    data, nodes, edges = make_data()
    base = pd.read_csv(BASE_FILE, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    train_x = data.x[data.train_mask]
    mean = train_x.mean(dim=0, keepdim=True)
    std = train_x.std(dim=0, keepdim=True)
    std[std == 0] = 1.0
    data.x = (data.x - mean) / std

    model = GraphSAGE(data.num_node_features, HIDDEN_DIM, 2, DROPOUT)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)

    best_state = None
    best_val_f1 = -1.0
    best_epoch = -1
    patience_left = PATIENCE
    history = []

    for epoch in range(1, EPOCHS + 1):
        model.train()
        optimizer.zero_grad()
        logits, _ = model(data.x, data.edge_index)
        loss = F.cross_entropy(logits[data.train_mask], data.y[data.train_mask])
        loss.backward()
        optimizer.step()

        train_loss, train_metrics, _, _ = evaluate(model, data, data.train_mask)
        val_loss, val_metrics, _, _ = evaluate(model, data, data.val_mask)
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "train_f1": train_metrics["f1"],
                "val_f1": val_metrics["f1"],
            }
        )

        if val_metrics["f1"] > best_val_f1:
            best_val_f1 = val_metrics["f1"]
            best_epoch = epoch
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_left = PATIENCE
        else:
            patience_left -= 1
            if patience_left <= 0:
                break

    if best_state is None:
        raise RuntimeError("Training did not produce a best model state.")
    model.load_state_dict(best_state)

    train_loss, train_metrics, train_prob, train_emb = evaluate(model, data, data.train_mask)
    val_loss, val_metrics, val_prob, val_emb = evaluate(model, data, data.val_mask)
    test_loss, test_metrics, test_prob, embeddings = evaluate(model, data, data.test_mask)

    model.eval()
    with torch.no_grad():
        logits, embeddings = model(data.x, data.edge_index)
        prob = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
        pred = logits.argmax(dim=1).cpu().numpy()
        emb_np = embeddings.cpu().numpy()

    pred_df = pd.DataFrame(
        {
            "company_id": nodes["company_id"],
            "company_name": nodes["company_name"],
            "true_label": nodes["label"].map({0: "否", 1: "是"}),
            "pred_label": pd.Series(pred).map({0: "否", 1: "是"}),
            "pred_prob": prob,
        }
    ).sort_values("pred_prob", ascending=False)
    pred_df.to_csv(PRED_FILE, index=False, encoding="utf-8-sig")

    embed_cols = {f"emb_{i}": emb_np[:, i] for i in range(emb_np.shape[1])}
    embed_df = pd.DataFrame({"company_id": nodes["company_id"], **embed_cols})
    embed_df.to_csv(EMBED_FILE, index=False, encoding="utf-8-sig")

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "mean": mean,
            "std": std,
            "config": {
                "hidden_dim": HIDDEN_DIM,
                "dropout": DROPOUT,
                "lr": LR,
                "weight_decay": WEIGHT_DECAY,
                "epochs": EPOCHS,
                "patience": PATIENCE,
                "seed": SEED,
            },
        },
        MODEL_FILE,
    )

    report = {
        "num_nodes": int(len(nodes)),
        "num_edges": int(len(edges)),
        "positive_labels": int(nodes["label"].sum()),
        "train_size": int(nodes["train_mask"].sum()),
        "val_size": int(nodes["val_mask"].sum()),
        "test_size": int(nodes["test_mask"].sum()),
        "best_epoch": best_epoch,
        "config": {
            "hidden_dim": HIDDEN_DIM,
            "dropout": DROPOUT,
            "lr": LR,
            "weight_decay": WEIGHT_DECAY,
            "epochs": EPOCHS,
            "patience": PATIENCE,
            "seed": SEED,
        },
        "train_metrics": train_metrics,
        "val_metrics": val_metrics,
        "test_metrics": test_metrics,
        "history_tail": history[-10:],
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    top20_df = build_top20(pred_df, base)
    top20_df.to_csv(TOP20_FILE, index=False, encoding="utf-8-sig")

    print(f"Saved predictions to: {PRED_FILE}")
    print(f"Saved embeddings to: {EMBED_FILE}")
    print(f"Saved report to: {REPORT_FILE}")
    print(f"Saved model to: {MODEL_FILE}")
    print(f"Saved recommendations to: {TOP20_FILE}")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
