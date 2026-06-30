# FinChain-Agent GitHub 上传清单

## 建议上传

这些文件建议保留在仓库中，足够支撑 GitHub Pages 自动构建与发布：

- `.github/workflows/deploy-finchain-pages.yml`
- `prototype_app/backend/repository.py`
- `prototype_app/backend/server.py`
- `prototype_app/build_static_site.py`
- `prototype_app/frontend/index.html`
- `prototype_app/frontend/styles.css`
- `prototype_app/frontend/app.js`
- `prototype_app/README.md`
- `prototype_app/DEPLOY_GITHUB_PAGES.md`
- `outputs/model_results/*.csv`
- `outputs/model_results/*.json`
- `outputs/graphsage/graphsage_report.json`
- `outputs/low_altitude_pipeline/企业主表.csv`
- `outputs/master_panel_results/39家企业画像总表.csv`
- `outputs/master_panel_results/39家企业画像静态总表.csv`

## 可以不上传

这些内容不是 GitHub Pages 发布所必需，可以不放进公开仓库：

- `neo4j/.venv/`
- 所有 `__pycache__/`
- 所有 `*.pyc`
- 所有 `.DS_Store`
- 本地临时运行目录或缓存

## 视情况决定

这些文件取决于你是否想把完整比赛资料一起公开：

- `文件资料/`
- `outputs/final_delivery/`
- `outputs/比赛提交材料_最终版/`
- `1998～2024年中国城市统计年鉴地级市面板数据.dta`
- `低空经济企业.xlsx`

如果你的目标只是发布网页，以上资料都可以不传。

## 最小公开仓库建议

如果你想让仓库更轻、更像展示项目，最小集可以是：

1. `prototype_app/`
2. `.github/workflows/deploy-finchain-pages.yml`
3. 仅保留构建静态站点所需的 `outputs/` 子集

## 推送前检查

推送前建议本地确认：

```bash
python3 prototype_app/build_static_site.py
```

并检查以下文件是否存在：

- `prototype_app/site/index.html`
- `prototype_app/site/data/summary.json`
- `prototype_app/site/data/companies.json`

## 发布后网址

GitHub Pages 地址通常为：

```text
https://<GitHub用户名>.github.io/<仓库名>/
```
