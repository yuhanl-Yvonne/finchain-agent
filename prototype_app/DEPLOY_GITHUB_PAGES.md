# FinChain-Agent GitHub Pages 部署说明

当前仓库已经补齐 GitHub Pages 所需文件：

- 静态构建脚本：`prototype_app/build_static_site.py`
- 自动发布工作流：`.github/workflows/deploy-finchain-pages.yml`
- 静态产物目录：`prototype_app/site`

## 一次性准备

1. 将当前项目推送到 GitHub 仓库。
2. 确保默认分支为 `main` 或 `master`。
3. 打开仓库页面：
   - `Settings`
   - `Pages`
4. 在 `Build and deployment` 中选择：
   - `Source: GitHub Actions`

## 发布逻辑

每次你向 `main` 或 `master` 推送以下内容时，会自动重新发布：

- `prototype_app/**`
- `outputs/**`
- `.github/workflows/deploy-finchain-pages.yml`

工作流会自动执行：

1. 安装 Python
2. 运行 `python prototype_app/build_static_site.py`
3. 生成 `prototype_app/site`
4. 将 `site/` 发布到 GitHub Pages

## 发布后的静态网址

GitHub Pages 默认网址通常为：

```text
https://<你的GitHub用户名>.github.io/<仓库名>/
```

例如：

```text
https://yourname.github.io/finchain-agent/
```

如果仓库名是用户主页仓库 `<用户名>.github.io`，则网址会变为：

```text
https://<你的GitHub用户名>.github.io/
```

## 本地预检查

在推送前可以本地执行：

```bash
python3 prototype_app/build_static_site.py
```

然后检查：

- `prototype_app/site/index.html`
- `prototype_app/site/data/summary.json`
- `prototype_app/site/data/companies.json`

## 当前限制

- 当前公开版本仅展示 39 家样本企业
- 不包含实时后端 API
- GitHub Pages 仅托管静态页面，不运行 Python 服务

## 适用场景

- 比赛展示
- 对外演示链接
- 简历 / 作品集展示页

如果后续需要接真实后端、数据库、登录或动态查询，应切换到服务化部署方案。
