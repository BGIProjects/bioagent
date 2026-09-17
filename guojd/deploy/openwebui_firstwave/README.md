# Open WebUI 第一波 overlay（2026-09-11）

从 liufangzhou 最新分析页 / agent 拷贝后修改，供合入 cyclone `/data/bioagent`。

当前账号对 `/data/bioagent` 与 liufangzhou 仓无写权限。live `:5173` 在有写权限的同事执行 `./sync_to_cyclone.sh` 并重启前，仍是旧代码。

## 本轮改动

- W2 默认 `workflow2_virusid`（不再是 2026db）
- 分析页可同时选 1 对或多对 FASTQ；testdata 出现在文件树根
- 右侧「知识/专项」：ICTV kb.jsonl / RVA 只读查询；定种与 RVA 确认后才计算
- 目标含 W6 `annotation_delivery`；第一波按钮选 W1–W4+W6

## 合入 cyclone

需要能写 `/data/bioagent` 的账号：

```bash
bash /data/user/guojindan/Projects/XvirMind/deploy/openwebui_firstwave/sync_to_cyclone.sh
```

然后重启 Open WebUI 前端 5173、后端 8080、adapter 8001。确保 MCP `:8766/:8767` 仍在跑。

## 测试包

`/data/user/guojindan/Projects/XvirMind/testdata/README.md`


## 第二波（已打进同一 overlay）

分析页新增「治理」：成员、分块上传、W1–W4+W6 队列、暂停/恢复、规则、打回。
报告模板会注入定种 / RVA / kb.jsonl 引用（`specialist.json`）。
知识 Demo 不依赖 cyclone：http://127.0.0.1:3080/knowledge
