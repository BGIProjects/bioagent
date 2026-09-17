# W1 QC Portable

跨平台 W1 上游数据质量报告工具（与 XvirBench 现行版输出一致）。

完整规范与**全部源码**见上级文档：

- [`../W1_QC_REPORT_GUIDE.md`](../W1_QC_REPORT_GUIDE.md)
- 打包：[`../w1_qc_portable.tar.gz`](../w1_qc_portable.tar.gz)

## Quick start

```bash
pip install -r requirements.txt
python run_w1_qc_report.py --batch-dir /path/to/batch --host rat --out-dir ./out
```

批次目录需含 `sampleinfo.tsv`（或 `cohorts/sampleinfo.tsv`）以及  
`qc_upstream_run.tsv` + `qc_upstream_sample.tsv`（在 `harmonized/workflow1/` 或根目录）。
