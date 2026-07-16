# 诊断意见书

## 本次实现

`/analysis` 中的 BioAgent 在一次分析成功完成后，会在最终回复末尾生成隐藏的 `diagnostic_report` 控制块。控制块只包含一个无样式的语义化 HTML fragment：

```html
<article class="diagnostic-report">
  <header>
    <h1>诊断意见书</h1>
    <p class="review-status">待专家审核</p>
  </header>
  <section>
    <h2>实际分析范围</h2>
    <p>仅描述本次确实完成的分析步骤。</p>
  </section>
</article>
```

Agent runtime 会拦截该 fragment，验证标签和属性，补充统一的 A4 HTML 文档结构与极简样式，然后写入：

```text
<run_dir>/diagnostic-opinion.html
```

同时，runtime 会更新 `.bioagent/state.json` 的 `report` 字段，并向 Open WebUI 发送一个 `diagnostic_report` structured output item。报告正文不会存入 WebUI 数据库；数据库只保存报告标题、run、文件名和生成时间等元数据。

Open WebUI 后端只允许下载 `BIOAGENT_RUN_ROOT` 下固定名称的报告文件。`/analysis` 根据 structured output 显示“诊断意见书”卡片和“下载 HTML”按钮。

## 内容边界

- 只在 `execution.status=completed` 且 `execution.ok=true` 时生成报告。
- 只呈现当前 run 和当前对话中有证据支持的内容。
- 用户跳过的质控、组装、分类等步骤不得出现在报告中。
- 仅有质控或组装结果时，不得推断病毒分类或病原学诊断。
- 未知样本信息、指标、分类结果和证据不得补写占位内容。
- 第一版不补生成历史报告，不支持重生成、在线预览、编辑、签章或签发。

## 子项目改动

- `agent`：增加报告控制块协议、HTML fragment 验证、统一样式包装、run 文件与状态写入，以及 structured output。
- `open-webui`：增加受保护的报告下载 API、report output 类型验证和 `/analysis` 下载卡片。
- 主 repo：记录协议；提交本次改动时，再记录两个 submodule 的对应提交。

## 未来病毒分类与多证据研判

本次实现不约束病毒分类子 agent 的调度方式或结果 schema。后续只有在分类结果已经成为当前成功 run 的可靠输出后，编排层才应把这些结果交给最终报告生成步骤。

报告生成者可在同一个 `<article>` 中增加新的 `<section>`，例如“分类判定”或“多证据研判”，并使用现有的标题、段落、列表、描述列表和表格标签表达结果。只要继续遵守相同的 HTML fragment 协议，runtime 样式、报告文件、Open WebUI 下载接口和前端卡片均无需修改。

建议后续保留以下原则：

- 分类结论必须能追溯到明确的 run 产物或结构化证据。
- 多证据内容应区分证据事实、综合判断与局限性。
- 未执行、失败或仍待确认的证据不得表述为已完成结论。
- 子 agent 只负责提供可靠结果；最终报告仍由统一的报告生成步骤汇总，避免多个组件分别写同一个 HTML 文件。
