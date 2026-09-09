# 本轮验证与复现记录

最新包含五批修复，基于 `2615924`，独立工作分支 `codex/product-quality-review`。原桌面项目未修改。

| 检查 | 结果 | 实际覆盖和限制 |
| --- | --- | --- |
| 修改前后端基线 | 236 passed | 实际本地重跑；数据库和真实模型默认跳过 |
| 修改后后端 | 339 passed，27 skipped，1 deselected | 全量普通检查；另外 25 个子场景通过。跳过不计为通过 |
| PostgreSQL | 25 passed | 使用独立 `rentwise_review_test`；包括会话撤销/隔离及费用单位冻结/审计、失败清理持久重试和卷隔离、限额/请求边界、并发保护、图片恢复与迁移回退/升级；模拟模型，没有付费请求 |
| Ruff | 通过 | 后端源码、测试、脚本 |
| git diff --check | 通过 | 空白与补丁格式 |
| 前端 lint / TypeScript | 通过 | Node 22.23.2、npm 10.9.8 |
| 前端正式构建 | 通过 | 明确使用 Next.js 的 Webpack 构建；Google 字体依赖已移除 |
| 浏览器 | 24 passed | 原流程、会话退出/多标签页/失效重试、费用周期修正、选图累积/限制、手机导入说明、长度限制及中断检查不自动重试 |
| 真实模型 | **未通过，结果不完整** | 放行网络后 20 次请求：3 完成、17 服务不可用；关闭 SDK 自动重试；未追加调用 |
| GitHub CI | 已推送的 `a2be6f9` 通过 | [Actions](https://github.com/YingqianChen/RentWise-dev/actions/runs/34322984733)；第五批以其对应提交的 Actions 结果为准，不能把旧 CI 结果归给新代码 |
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
- 后端仍有 passlib crypt 和 Starlette/httpx 的弃用提示；启动钩子已迁移为 lifespan；本轮没有为消除提示擅自升级整套依赖。
- 本轮没有真人可用性测试、公开部署验收、完整安全审计或真实模型准确率证明。
- 已验证记录删除后的清理失败重试、回滚及并发/卷隔离；上传尚未持久入库时的故障、历史孤儿文件和第三方留存仍需独立处理。

第二批实现与 review 记录见 `2026-09-09-reliability-review.md`。第二批测试均使用离线或本地模拟，没有追加真实模型请求。

最新功能及运行要求见[第五批审查](2026-09-09-session-review.md)。迁移至 `20260909_0020` 只在独立测试库执行，真实环境尚未部署。追加真实模型请求为零；既有 20 次授权已使用完毕。
