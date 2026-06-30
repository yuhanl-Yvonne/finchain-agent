# FinChain-Agent 上传与部署流程

本文档分为两部分：

1. 本地项目整理与上传流程
2. GitHub Pages 部署流程

适用目标：

- 将当前 FinChain-Agent 静态展示页发布为可公开访问的网页
- 保留后续继续扩展服务化版本的代码基础

---

## 一、本地项目整理与上传流程

### 1. 确认本地项目结构

当前 GitHub Pages 发布所依赖的关键内容包括：

- `.github/workflows/deploy-finchain-pages.yml`
- `prototype_app/`
- `outputs/` 中用于构建静态站点的必要数据

核心说明文件：

- `prototype_app/README.md`
- `prototype_app/DEPLOY_GITHUB_PAGES.md`
- `prototype_app/GITHUB_UPLOAD_CHECKLIST.md`

### 2. 本地构建静态站点

在项目根目录执行：

```bash
python3 prototype_app/build_static_site.py
```

执行成功后，检查以下文件是否存在：

```text
prototype_app/site/index.html
prototype_app/site/styles.css
prototype_app/site/app.js
prototype_app/site/data/summary.json
prototype_app/site/data/companies.json
prototype_app/site/data/company/*.json
```

### 3. 建议上传的目录与文件

建议至少上传以下内容：

```text
.github/workflows/deploy-finchain-pages.yml
prototype_app/
outputs/model_results/
outputs/graphsage/graphsage_report.json
outputs/low_altitude_pipeline/企业主表.csv
outputs/master_panel_results/39家企业画像总表.csv
outputs/master_panel_results/39家企业画像静态总表.csv
```

### 4. 不建议上传的内容

以下内容不是发布静态网页所必需：

```text
neo4j/.venv/
__pycache__/
*.pyc
.DS_Store
文件资料/
outputs/final_delivery/
outputs/比赛提交材料_最终版/
1998～2024年中国城市统计年鉴地级市面板数据.dta
低空经济企业.xlsx
```

这些内容可以保留在本地，不必公开上传。

### 5. 创建 GitHub 仓库

在 GitHub 新建一个仓库，例如：

```text
finchain-agent
```

仓库建议设置为：

- Public：如果你需要公开访问网页
- Private：如果只是先测试流程

如果使用 GitHub Pages 对外展示，最终通常建议使用 Public 仓库。

### 6. 本地初始化 Git 并推送

如果当前目录还不是 Git 仓库，可在项目根目录执行：

```bash
git init
git add .
git commit -m "Initial commit for FinChain-Agent Pages deployment"
git branch -M main
git remote add origin https://github.com/<你的GitHub用户名>/<仓库名>.git
git push -u origin main
```

如果你使用 SSH，也可以改为：

```bash
git remote add origin git@github.com:<你的GitHub用户名>/<仓库名>.git
git push -u origin main
```

### 7. 后续更新流程

如果后面你修改了页面、样式或 39 家样本数据，重复以下步骤即可：

```bash
python3 prototype_app/build_static_site.py
git add .
git commit -m "Update FinChain-Agent static site"
git push
```

---

## 二、GitHub Pages 部署流程

### 1. 打开 GitHub Pages 设置

进入你的 GitHub 仓库页面，依次点击：

```text
Settings > Pages
```

### 2. 设置发布来源

在 `Build and deployment` 区域中，将 `Source` 设置为：

```text
GitHub Actions
```

当前仓库中已经有自动发布工作流：

```text
.github/workflows/deploy-finchain-pages.yml
```

不需要你手工再创建。

### 3. 自动发布的执行逻辑

当你向 `main` 或 `master` 推送以下内容时，GitHub Actions 会自动执行部署：

- `prototype_app/**`
- `outputs/**`
- `.github/workflows/deploy-finchain-pages.yml`

工作流会自动完成：

1. 拉取仓库代码
2. 安装 Python 3.11
3. 执行 `python prototype_app/build_static_site.py`
4. 生成 `prototype_app/site`
5. 将 `site/` 发布到 GitHub Pages

### 4. 查看部署状态

推送完成后，在仓库页面点击：

```text
Actions
```

查看 `Deploy FinChain-Agent Pages` 工作流是否成功。

如果构建成功，GitHub Pages 会生成公网地址。

### 5. 获取最终网址

GitHub Pages 一般会给出如下网址：

```text
https://<你的GitHub用户名>.github.io/<仓库名>/
```

例如：

```text
https://yourname.github.io/finchain-agent/
```

如果你的仓库名正好是：

```text
<你的GitHub用户名>.github.io
```

那么网址会变成：

```text
https://<你的GitHub用户名>.github.io/
```

### 6. 首次发布后的检查项

打开网址后，确认以下内容正常：

- 首页正常加载
- 39 家样本企业正常显示
- A/B/C/D 分层正常显示
- 企业详情可点击切换
- 全局解释区正常显示
- 页面没有出现 `/api/*` 请求失败

### 7. 常见问题排查

如果 GitHub Pages 打开后空白或数据不显示，优先检查：

1. `Actions` 工作流是否成功执行
2. `Settings > Pages` 是否选择了 `GitHub Actions`
3. `prototype_app/build_static_site.py` 是否能在本地正常运行
4. `site/index.html` 是否已切换为静态模式
5. 构建所需的 `outputs/` 数据文件是否已上传到仓库

### 8. 更新网页内容

后续网页内容更新时，流程保持不变：

```bash
python3 prototype_app/build_static_site.py
git add .
git commit -m "Refresh FinChain-Agent Pages site"
git push
```

推送后 GitHub Actions 会自动重新部署。

---

## 三、建议使用方式

如果你的当前目标是比赛展示，建议采用下面这套最稳流程：

1. 保留当前本地服务版作为开发环境
2. 使用 `build_static_site.py` 生成静态站点
3. 将静态版通过 GitHub Pages 对外发布
4. 后续若继续产品化，再单独部署服务化版本

---

## 四、最简执行版

如果你只想快速完成发布，按下面执行即可：

```bash
python3 prototype_app/build_static_site.py
git init
git add .
git commit -m "Initial FinChain-Agent Pages release"
git branch -M main
git remote add origin https://github.com/<你的GitHub用户名>/<仓库名>.git
git push -u origin main
```

然后到 GitHub：

```text
Settings > Pages > Source > GitHub Actions
```

等待 Actions 跑完，即可获得公网网址。
