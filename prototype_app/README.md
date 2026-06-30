# FinChain-Agent 原型与公开版说明

当前目录已拆分为两条可复用交付路径：

- `本地服务版`：保留 Python API，适合继续联调、接后端能力与后续产品化扩展。
- `静态公开版`：把 39 家样本与汇总数据固化为 JSON，可直接部署到 GitHub Pages、Vercel、Netlify 等平台。

## 目录结构

- `backend/server.py`
  - 本地服务入口
- `backend/repository.py`
  - 共享数据整理与 39 家样本分层逻辑
- `frontend/`
  - 前端页面与样式
- `build_static_site.py`
  - 静态站点构建脚本
- `site/`
  - 静态站点产物目录

## 本地服务版启动

在工作区根目录执行：

```bash
python3 prototype_app/backend/server.py
```

默认地址：

```text
http://127.0.0.1:8765
```

当前后端已支持：

- 默认监听 `0.0.0.0`
- 通过环境变量控制端口：
  - `PORT`
  - `FINCHAIN_PORT`
  - `FINCHAIN_HOST`

示例：

```bash
PORT=9000 FINCHAIN_HOST=0.0.0.0 python3 prototype_app/backend/server.py
```

## 静态公开版构建

执行：

```bash
python3 prototype_app/build_static_site.py
```

构建完成后会生成：

```text
prototype_app/site/
```

其中包含：

- `index.html`
- `styles.css`
- `app.js`
- `data/summary.json`
- `data/companies.json`
- `data/company/*.json`

静态版前端默认使用 `static` 数据模式，不依赖本地 Python API。

### GitHub Pages 发布

仓库内已提供 GitHub Pages 自动发布工作流：

- `.github/workflows/deploy-finchain-pages.yml`

详细说明见：

- `prototype_app/DEPLOY_GITHUB_PAGES.md`
- `prototype_app/GITHUB_UPLOAD_CHECKLIST.md`
- `prototype_app/UPLOAD_AND_DEPLOY_STEPS.md`

推送到 GitHub 的 `main` 或 `master` 后，可在仓库 `Settings > Pages` 中选择 `GitHub Actions` 作为发布来源。

## 前端数据模式

前端支持两种模式：

- `api`
  - 读取 `/api/summary`、`/api/companies`、`/api/company/{id}`
- `static`
  - 读取 `/data/*.json`

默认行为：

- `frontend/index.html`：默认 `api`
- `site/index.html`：构建后自动切换为 `static`

可用全局变量：

```js
window.APP_DATA_MODE = "api" | "static";
window.APP_API_BASE = "";
window.APP_STATIC_BASE = ".";
```

## 当前公开范围

- 仅保留 39 家样本企业
- 保留 A/B/C/D = 10/10/10/9 分层
- 保留语义化 SHAP 标签
- 不公开 466 家全量结果

## 后续可扩展方向

- 将本地文件数据源替换为数据库或模型服务
- 将标准库 HTTP 服务迁移到正式 Web 框架
- 接入鉴权、实时查询与图数据库能力
