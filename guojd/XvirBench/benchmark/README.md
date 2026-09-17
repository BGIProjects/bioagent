# XvirBench/benchmark — 全流程分析体系

工作流跑完之后：提取指标与样本 Meta → 统计/SCI 风格 ggplot2 图/生物学解读 → 结构化 TSV 与 HTML。

**标准化方案（逻辑与文件对应）**

- [PLATFORM_STANDARDIZATION_SCHEME.md](PLATFORM_STANDARDIZATION_SCHEME.md) — 流程 / 提取 / 提示词 / 报告的逻辑与文件对应（供其他平台标准化）

**唯一规范（提示词 + 全部脚本）**

- [FULL_PIPELINE_ANALYSIS_SYSTEM.md](FULL_PIPELINE_ANALYSIS_SYSTEM.md)
- [FULL_PIPELINE_ANALYSIS_SYSTEM.html](FULL_PIPELINE_ANALYSIS_SYSTEM.html)

**可运行包**：`package/run_full_pipeline_analysis.py`  
**示例报告**：[runs/pxy_V350399508/report.html](runs/pxy_V350399508/report.html) · [report.pdf](runs/pxy_V350399508/report.pdf)（横向 A4，图已嵌入）

```bash
export XVIRBENCH_ROOT=/data/user/guojindan/Projects/XvirMind/XvirBench
export PYTHONPATH=$XVIRBENCH_ROOT/benchmark/package:$XVIRBENCH_ROOT/scripts
python3 $XVIRBENCH_ROOT/benchmark/package/run_full_pipeline_analysis.py \
  --run-dir /data/user/guojindan/Projects/Workflows/benchmark/test/runs/pxy_V350399508 \
  --out-dir $XVIRBENCH_ROOT/benchmark/runs/pxy_V350399508 \
  --batch-id pxy_V350399508
```

与 `docs/w1_qc_portable` 的关系：后者只规范 W1 评分与 4 张图；本目录把同一套「提示词 + 源码附录」扩展到 W1–W7，并改为「缺失流程整章跳过」。
