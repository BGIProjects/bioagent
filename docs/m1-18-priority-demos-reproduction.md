# M1 第十八轮优先 Demo 复现记录

日期：2026-09-30。本轮只完成端到端科学报告、本地工具库调用、Workflow 1 read-QC 技能原样／受控修改三项 Demo；不新增第二个工具、通用市场、多样本推论、本地 LLM、正式专家审核或 W3–W6 重算。

## 输入、版本与运行

输入为 `BJ-2024-615_{1,2}.fastq.gz`，原文件大小 126,682,083／172,927,531 bytes。为符合 logical data root 准入，只新增 `/data/user/liufangzhou/datasets/m1-18-flu-ngs` 指向既有 allowlisted NGS 目录的 symlink；没有复制、改写或搬动 FASTQ。

| 项目                  | 值                                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------ |
| 工具                  | `fastp@1.3.2`                                                                                                |
| 工具目录 digest       | `16c4fd7daa9f79b842d0123714479b10346cb6f8b419ff0bf49cf3f2614922bf`                                           |
| 技能                  | `bioagent-w1-read-qc@1.0.0`                                                                                  |
| manifest digest       | `b3ba3cba61673853ede6f2f90f2c13e1a61c8f31717a15d56066348083c38dfc`                                           |
| `SKILL.md` digest     | `7b2fa18f78d2b97862e8ba22c04227f64fb9bd263fec1b7208f3a1ed5245cd49`                                           |
| 默认 compiled digest  | `271dcb10ae52a26f9d3bd4d05a5b4e521d5a93f86777923911480cf3c191964c`                                           |
| 80 bp compiled digest | `cc0e9da89f3749c0647cda033d0c9fe4d23c3de4a7ac82d5706ebdd3eaaf50ca`                                           |
| 文献 release          | `scientific-report-literature-v1`；digest `0ec408ee618f2642b09e7938ea2b30a30bef93f20b88a7773da538c2b7d80658` |

实际 run：

| Run                                       | 范围                                   | 状态／耗时                                                                                                  |
| ----------------------------------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `analysis-m118-priority-full-20260930`    | 默认技能，W1→W2                        | 启动失败尝试；W1 完成后 W2 因 `hmmsearch` 未在 phase `PATH` 中而失败，00:46:42–00:49:33。该结果未用于验收。 |
| `analysis-m118-priority-full-r2-20260930` | 默认技能，W1→W2                        | 成功；00:52:24–03:31:18，共 2:38:54。W1 为 2:29，W2 为 2:36:20。                                            |
| `analysis-m118-priority-qc80-20260930`    | `length_required=80`，只执行 `read_qc` | 成功；03:31:27–03:32:07，共 40 秒，W1 phase 为 36 秒。                                                      |

首次失败没有重写 Workflow 2 源码；runner 改为从 run-local workflow config 的 `software` 绝对入口补齐 phase `PATH`，修正版实际通过 `hmmsearch` 后继续 NR 搜寻。技能修改 run 在修正版 W1 完成并进入 W2 后建立，由同一持久 scheduler 排在 W2 后执行。

## 报告与确定性

完整 run 提取 93 个 facts：fastp 前后分别为 5,536,168／4,285,442 reads，保留率 77.41%；rRNA 过滤保留率 99.97%；W2 得到 1 个候选，`Profile_cov=0.9956331877729258`、CheckV completeness 37.97、NR identity 99.868。分类证据为 Orthomyxoviridae／Influenza A virus 数据库最佳命中，报告明确不据此确认 H/N 亚型。

科学报告 facts digest 为 `1efe1acfed958572fcd0ce26ca14a6368b0b46577e67437adfcaf4d9a62b5e25`，reasoning cache key 为 `59a4305c3e3675a72bec57564ef967e7ca5ddad33644bf95a6b22a97109da14b`。第二次生成命中已验证 reasoning plan；两次 facts JSON 与 HTML 逐字节相同，数字、citation ID、locator 及出现顺序不变。

| 产物                 | SHA-256                                                                                                                                |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| 科学报告 HTML        | `800797fe57877a3f894db08daa266d75fd0754e90f39ad65752187fe5802db7b`                                                                     |
| 科学报告 PDF         | `5d7175490841cb5398824362c137f959678b2bbfda153f25929ac4aed8b6e020`                                                                     |
| facts JSON           | `ce2d57ab70b55d17b5aa83078a11b8287ddbfc1b124af319645081d8d68a8265`                                                                     |
| 文献快照             | `cd0774760461ce6cc0d3ed5c5e2103dbfa01b674f63892d0fd2a0ac416540190`                                                                     |
| reasoning plan       | `704ed880e3b5150cfc42cc5b18b9b8e999460c1c616ca1529c778dfe94acf8b1`                                                                     |
| 工具 Demo JSON／HTML | `805129d4841d7424200c352e91e871a3741cb19b12337e50ae21a2e6b700b86d`／`c8d255a5a1eda2f5a37f284dc5ebb9efeb54f8efc7d2882a4987e0a6ba450df0` |
| 技能 Demo JSON／HTML | `e6189ec814ef26511b9910f3f43dc497d819bafee4e2e7b60183435254f0e38a`／`2fab90de3e88d88581bb833a3db3a5a2b7f30101826a913438b71bbf69c37621` |

默认／80 bp run 的 fastp 输出 artifact digest 分别为 `83000cc18fef5653a044c5b30e5edb121e40fb9bcdf3bd0b14fa23b612ee02da`／`39b423de20be24d4449f39c9587216757f40272d8c07404617245f3040600919`；后者保留 4,283,268 reads。去除 override 与其派生 digest 后，两份 compiled skill spec 完全一致。所有产物只登记在对应 run 的：

- `reports/standard/scientific/`
- `reports/standard/tool-demo/`
- `reports/standard/skill-demo/`

科学报告的 MiniMax 请求只有匿名 fact／source／claim ID；模型不能返回数字、文本、路径或新引用。本机验证器固定证据关系，确定性 renderer 才插入结果数字、分类文字与 locator。不匹配本地文献的类群或阈值固定输出“依据不足”；数据库 H/N 最佳命中不得作为亚型确认。

## 容量与验证

启动及 W1→W2 切换时本机 `/tmp` 可用约 186.8 GiB，Cyclone `/data` 可用约 364 GiB、NVMe 可用约 43.5 GiB。W2 在 01:24:59、01:55:38、02:27:06、02:58 与 03:28:52 的半小时快照均高于阈值。最终快照为本机 `/tmp` 186.8 GiB、Cyclone `/data` 363.1 GiB、NVMe 43.5 GiB；三份本机服务日志最大仅 3,739 bytes，未达到 100 MiB 告警。两个验收 run 由同一 `bioagent-scheduler-20bc4c43bfc5` 持久 scheduler 依序执行；完整／修改版 run 分别占 619／263 MiB，没有传输 FASTQ 或大型中间结果。

复现入口：

```sh
./dev-services.sh start
curl -fsS http://127.0.0.1:8001/analysis/capabilities
curl -fsS 'http://127.0.0.1:8001/v1/analysis/runs/snapshot?run_dir=/data/user/liufangzhou/runs/<run-id>'
curl -fsS -H 'Content-Type: application/json' \
  -d '{"run_dir":"/data/user/liufangzhou/runs/<run-id>"}' \
  http://127.0.0.1:8001/v1/analysis/runs/priority-reports
curl -fsS -o report.html \
  'http://127.0.0.1:8001/v1/analysis/runs/artifact-report?run_dir=/data/user/liufangzhou/runs/<run-id>&kind=scientific&format=html'
```

最终验证为 Agent 264 passed、2 skipped，Backend 80 passed，Vitest 65 passed；变更文件 Ruff、Prettier、skill quick validation 与 diff whitespace 检查均通过。沙箱内第一次 build 调用在前端编译前的 Pyodide metadata 下载阶段被本机代理权限阻断；随后在沙箱外执行一次完整的 `NODE_OPTIONS=--max-old-space-size=8192 npm run build` 并成功，完整输出保存在 `/tmp/bioagent-m1-18-frontend-build.log`。没有数据库 migration；`AGENTS.md` 未修改。
