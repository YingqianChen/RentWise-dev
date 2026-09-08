# 本轮验证与复现记录

基于 `2615924`，独立工作分支 `codex/product-quality-review`。原桌面项目未修改。

| 检查 | 结果 | 实际覆盖和限制 |
| --- | --- | --- |
| 修改前后端基线 | 236 passed | 实际本地重跑；数据库和真实模型默认跳过 |
| 修改后后端 | 279 passed，11 skipped，1 deselected | 全量普通检查；另外 25 个子场景通过。跳过不计为通过 |
| PostgreSQL | 9 passed | 使用新建 `rentwise_review_test`；包括图片失败重试/删除和计费周期变化；模拟模型，没有付费请求 |
| Ruff | 通过 | 后端源码、测试、脚本 |
| git diff --check | 通过 | 空白与补丁格式 |
| 前端 lint / TypeScript | 通过 | Node 22.23.2、npm 10.9.8 |
| 前端正式构建 | 通过 | 明确使用 Next.js 的 Webpack 构建；Google 字体依赖已移除 |
| 浏览器 | 15 passed | 原 13 项及新增选图累积/限制、手机导入说明和长度限制 |
| 真实模型 | **未通过，结果不完整** | 放行网络后 20 次请求：3 完成、17 服务不可用；关闭 SDK 自动重试；未追加调用 |
| GitHub CI | 未运行 | 本轮没有推送 |
| 当前依赖安全审计 | 未重新执行 | 没有新增或升级依赖，不沿用上个对话的“零漏洞”当成本轮结果 |

## 复现命令

前端需要项目规定的 Node 22；本机默认 `node` 是 26，勿直接把默认版本的结果视为规定环境的验证。

```sh
cd frontend
npm run check
```

后端使用 Python 3.11 及锁定依赖，在 `backend` 目录：

```sh
python -m pytest -q
ruff check app tests scripts
RUN_DB_INTEGRATION=1 python -m pytest tests/integration/test_db_flow.py -q
```

真实数据库测试只接受名称以 `_test` 结尾的数据库。这里的独立 `.env` 指向 `rentwise_review_test`，测试逐个创建并清理自己的合成账户，不清空开发数据库。

实际复用的本机 Python：`/Users/kk/Desktop/03_项目代码/RentWise/backend/.venv/bin/python`。
本机 Node 22：`/opt/homebrew/opt/node@22/bin/node`。未改全局 PATH 或 shell 配置。

真实评测的保存结果可通过 `python -m scripts.report_extraction_eval` 离线阅读。这条命令不调用模型。原报告仍在被 Git 忽略的 `backend/tests/evals/reports/extraction_last_run.json`。

## 已知验证边界

- Turbopack 在当前受限环境中无法创建内部临时端口；即使重试网络权限仍失败。Webpack 正式构建及浏览器流程通过，项目默认 build 已改成该路径。
- 前端仍提示未配置公开站点的 metadataBase；在选择部署域名时补充，现在没有编造一个域名。
- 后端仍有旧依赖/旧启动钩子的弃用提示；本轮没有为消除提示擅自升级整套依赖。
- 本轮没有真人可用性测试、公开部署验收、完整安全审计或真实模型准确率证明。
- 上传清理测试验证正常文件系统；清理失败后的持久重试、第三方留存和历史孤儿文件清理仍待完成。
