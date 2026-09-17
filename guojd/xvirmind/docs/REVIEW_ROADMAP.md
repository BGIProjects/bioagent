# 对 bioagent-implementation-roadmap (1).md 的审阅

结论：可以作为三轨建设提示词使用，比 v1.0 清单更接近私有化交付，但有几处必须改，否则会把实施带偏。

## 必须修正

1. **引用了不存在的设计文件。** 文中主依据写成 `bioagent-top-level-design-new.html`，docs 里实际是 `bioagent-top-level-design.html`（v1.1）。评价报告 `XvirMind_建设情况总结评价_20260910.html` 也在 docs 中，第 1.3 节说「当前不在 docs」已经过时。
2. **和本次明确需求冲突。** C0 / 第 7 节把 DeepSeek Harness 写成「按需、非近期必交付」；本次要求前端改为 DeepSeek Harness，并把 wangdaxi 的分类 / 注释作为 MCP 接入主 Agent。提示词应把这两项升为 M0/M1 的明确任务，而不是停在「条件接入」。
3. **专项 MCP 仍指向旧 TaxonAgent / Workflow 6。** 第 7 节默认注释走 Workflow 6、分类走本地检索或 5090 TaxonAgent。与现网资产不符：分类权威仓是 `/data/user/wangdaxi/Projects/virus_taxonomy`，注释权威仓是 `/data/user/wangdaxi/rna_virus_annotation`。二者应注册为独立 capability，而不是再包一层旧 TaxonAgent。
4. **代码落点仍全部写 liufangzhou / Open WebUI。** 作为提示词会诱导继续加厚可替换层。新方案代码应落在 `XvirMind/xvirmind`，Open WebUI 只当遗留对照。
5. **文件名带 `(1)`。** 不适合当唯一提示词路径，容易和 `bioagent-implementation-roadmap.md` 并排混淆。

## 内容上成立、应保留

- 三轨 + M0–M3 共同验收，知识/本地库不再卡在页面做完之后。
- 公共契约（ProviderRequest、CapabilityManifest、Citation、CandidateEvidence）先冻结。
- local_only、模型失败不挡确定性路径、计算须确认。
- 不做 RL 调度、不自动训练、不无限派生 Agent。
- 查询 MCP 与计算 MCP 分权，超时先查状态。

## 建议补进提示词的三条

- 主 Agent 只持有 MCP client；taxonomy / annotation 以只读查询默认开放，计算工具必须 confirm + 隔离 run root。
- DeepSeek Harness 只替换会话前端与 provider 传输，不获得 Bash/任意 workflow 权限。
- 官方 `dsh web` 默认 :3080；若现场 Node 过旧，允许使用架构兼容的宿主页，但插件契约保持不变。
