# M1 第十轮：小型工程知识引用复现记录

日期：2026-09-23。本轮只完成 B2 的工程引用切片，并重跑 C1 四类开发 smoke；完整 B2、C1、M0／M1 仍未完成。

## 实际范围

- Agent 发布 `engineering-knowledge-v1`：tracked JSON 与 registry 共 8,283 bytes，只含 capability catalog 可验证的能力、交付目标、artifact、fastp 参数与版本。启动时同时核对 catalog 身份及 release SHA-256，索引仅存在于内存 SQLite FTS5。
- `/analysis` 每次最多提供 4 段、每段 512 字。`respond` 只能引用本次 snapshot 的登记 ID；`clarify`／`propose_patch` 不带引用。伪造、重复、跨 snapshot、篡改、知识不足与检索不可用均 fail closed。
- `analysis_knowledge_citations@v1` 随既有项目聊天 output 保存，不新增表、migration、HTTP API、环境变量或向量库。Dashboard、ICTV／领域资料和 12 段 `pending` M0 资料保持原状。

## 验证结果

- Agent 全量：168 passed、2 skipped；跳过项仍是本机没有真实 workflow source／Snakemake 的既有集成测试。
- Backend 相关：107 tests，OK；Frontend Vitest：53 passed；Chrome 153／Cypress 13.17.0：19 passed，覆盖 1440px、390px 与历史引用恢复。
- Ruff 与 Prettier 对本轮文件通过；8 GiB Node heap production build 成功。

MiniMax 使用现有 16 个 `pending` 开发案例，每例一次、顺序执行、不重试；没有发送 FASTQ、私有路径或密钥：

| 任务       | schema 通过 | 工程校验通过 | 四例总延迟 |
| ---------- | ----------: | -----------: | ---------: |
| 意图／追问 |         3/4 |          3/4 |  45,473 ms |
| 受控改参   |         2/4 |          0/4 |  15,536 ms |
| 引用问答   |         4/4 |          4/4 |  25,540 ms |
| 证据说明   |         3/4 |          0/4 |  44,872 ms |

合计 schema 12/16、工程校验 7/16、provider 延迟 131,421 ms。失败为 4 个 `MODEL_SCHEMA_INVALID` 与 5 个 `HOST_VALIDATION_FAILED`；均未登记方案、报告或计算，也没有放宽校验、自动修复或补跑。结果不代表专家语义或生物学验收。

远端产物为 `Cyclone:/data/user/liufangzhou/runs/m1-minimax-20260923-engineering-citations`，共 8 文件、544,310 bytes：

```text
results.json  6c1808590163909d676e27f4d8bfd045391a8fd4cae776b85afeea5cc3fe2b1d
files.json    ebc1f89a52a902b26303adcddf286bd3793c49571a6c8462b0fd6d1bb4e2e737
```

## 复现

固定输入为 `agent/benchmarks/m1_development.json`（SHA-256 `668559eb0372db4316ef50a7fd46aa909895d2064e03359e1c3affcfcd11b2a3`）中的 `intent_clarification-1..4`、`controlled_patch-1..4`、`citation_qa-1..4` 与 `evidence_explanation-1..4`，以及命令中固定 SHA-256 的 M0 bundle。工程 release SHA-256 为 `45e70f06d04cd6bf1d748a991a959378acb64c6031f7fd08b576548ee097176e`。

本地关键验证命令如下；前端 build 是验证顺序中的最后一步，只执行一次：

```bash
cd agent
PYTHONPATH=. /Users/lfz/miniconda3/bin/conda run -n adapter pytest -q --ignore=tests/test_standard_report.py
PYTHONPATH=. /Users/lfz/miniconda3/envs/open-webui/bin/python -m pytest -q tests/test_standard_report.py
/Users/lfz/.local/bin/ruff check .

cd ../open-webui/backend
/Users/lfz/miniconda3/bin/conda run -n open-webui python -m unittest open_webui.utils.test_structured_stream

cd ..
npm exec vitest -- run src/lib/utils/analysisKnowledge.test.ts src/lib/components/analysis/AnalysisPage.contract.test.ts
CYPRESS_BASE_URL=http://127.0.0.1:5175 npm exec cypress -- run --browser chrome --spec cypress/e2e/project-ui.cy.js
NODE_OPTIONS=--max-old-space-size=8192 npm run build >/tmp/bioagent-m1-10-build.log 2>&1
```

MiniMax 从根目录执行；密钥只由交互 shell 提供。输出名称必须换成新的时间后缀，避免覆盖已有记录：

```bash
export PYTHONPATH=/Users/lfz/miniconda3/envs/open-webui/lib/python3.11/site-packages
M1_PYTHON=/Users/lfz/miniconda3/envs/adapter/bin/python
M1_RUN_ROOT=/data/user/liufangzhou/runs
M1_STAMP=$(date +%Y%m%d-%H%M%S)

"$M1_PYTHON" m1-check.py evaluate --allow-cloud \
  --ssh-host Cyclone --run-root "$M1_RUN_ROOT" \
  --bundle "$M1_RUN_ROOT/m0-baseline-20260912/bundle.json" \
  --bundle-sha256 43a2e26300d2cdd0e801669bc6d2ed9df1ce6d9380d0507702565bde2593da9e \
  --output "$M1_RUN_ROOT/m1-minimax-$M1_STAMP"
```

停止发布新对话后回退 Agent 与 Open WebUI 即可关闭入口；没有数据库状态要回滚。已有聊天中的受限引用 output 仍是普通历史 JSON，不会被新 release 改写；远端评测目录保留，不自动清理。

建议提交信息：根仓库 `docs: record lightweight M1 citation integration`；Agent `feat: add bounded engineering knowledge retrieval`；Open WebUI `feat: show project-scoped analysis citations`。
