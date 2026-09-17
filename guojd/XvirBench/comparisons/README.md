# 跨批次比较

存放**多个 benchmark 项目之间**的比较配置与输出，不存放单批次 harmonized 表。

## 约定

1. 单批次指标 → `batches/{batch_id}/harmonized/workflowN/*.tsv`
2. 跨批次比较脚本读取多个批次的 harmonized 表，输出到 `comparisons/{comparison_id}/`
3. 本目录在有多批次时再建子目录；当前仅 `vazyme_fragment_test` 一个活跃批次

## 抽取

```bash
# 单流程
python3 scripts/extract_metrics.py --batch-id vazyme_fragment_test -w workflow4

# 全量
python3 scripts/extract_metrics.py --batch-id vazyme_fragment_test --all

# 或批次内快捷脚本
bash batches/vazyme_fragment_test/scripts/extract.sh all
```
