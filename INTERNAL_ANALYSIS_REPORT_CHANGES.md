# `feat/internal-analysis-report` 分支變更記錄

本文檔記錄主 repo 的 `feat/internal-analysis-report` 分支中 `open-webui` 與 `agent` 兩個 submodule 的整體改動，作為後續開發、測試、審查與合併時的持續更新記錄。新增功能或調整既有設計時，應直接在相應章節追加或修訂內容，並同步更新 submodule commit 與驗證結果。

## Submodule 版本

| Submodule    | 分支                            | 基準分支 | 目前 commit |
| ------------ | ------------------------------- | -------- | ----------- |
| `open-webui` | `feat/internal-analysis-report` | `bgi`    | `8fc723985` |
| `agent`      | `feat/internal-analysis-report` | `main`   | `e126c7b`   |

## `open-webui` 改動

### 對話輸入與 IME

- 修復 BioAgent 聊天輸入框在中文、日文等輸入法仍處於 composition 階段時按下 Enter 會意外提交訊息的問題。
- 分析檔案樹提交的伺服器檔案以 `server_path` metadata 保存路徑、大小、修改時間及 `analysis_file_tree` 來源，使技術報告可以區分檔案選擇器、一般附件與聊天文字中的手動路徑。

### 分析 run 狀態與管理員接口

- 分析 run 狀態對管理員增加內部技術報告是否可用的資訊，一般使用者不會取得該欄位。
- 新增管理員限定的 `GET /analysis/runs/internal-report` endpoint，嚴格驗證 run root、state 中的 chat 關聯及 telemetry 版本，拒絕路徑逃逸、chat/run 不匹配與舊 state。
- 保持既有診斷意見書 endpoint 與一般使用者流程不變，原始 telemetry JSON 僅保存在 run 的 `.bioagent/` 目錄。

### 內部技術報告

- 後端以 DB 對話、run state、telemetry 與 agent trace 確定性組合自包含 HTML 報告，不使用 agent 撰寫報告。
- 報告包含檔案管理、使用者與 AI 交互時間線、方案 revision 差異、執行階段、job 級時間與資源、軟體命令與版本、輸入輸出 manifest、Fastp、去 rRNA、組裝及最終過濾指標。
- 長度分布以內嵌 SVG 箱線圖呈現 Q1、中位數與 Q3；缺少或未完成的產物顯示「未產生」，不推測數值。
- job 資源明細表使用專屬 `job-table`，資源欄最小寬度為 `360px`，資源內容以縮排 JSON 顯示並保留水平滾動。
- 使用者與 AI 交互表使用專屬 `conversation-table`，狀態欄最小寬度為 `72px`、置中且禁止字內換行，不影響其他報告表格。
- 所有對話、路徑、命令與資源內容均經 HTML escaping，螢幕與列印共用主要欄寬規則。

### 診斷意見書

- 交付報告不再由 AI 撰寫 HTML；後端根據成功 run 的 state 與版本化 workflow1 telemetry 即時確定性生成自包含 HTML。
- 報告固定包含摘要、分析範圍、樣本輸入、S0–S4 結果、四個內嵌 SVG 圖位、結果邊界、真實產物及科研用途聲明；未執行與未產生資料均明確標示，不以 0 代替。
- reads 統一以單條序列計數並顯示為 `M reads`，雙端資料另列 `M pairs`；測序 bases 顯示為 `Gb`，比例保留兩位小數，整數使用千分位。
- 報告僅陳述客觀質控與組裝結果，不套用 portable 的批次綜合評分，也不從上游結果推導病原分類或病因學結論。
- 診斷意見書 endpoint 不再讀取 run 內由模型生成的 HTML 檔，而是驗證成功終態、workflow、report schema 與 telemetry 後即時渲染。
- 圖表為條形軌道與右側數值保留固定獨立欄位，滿值、近滿值、短值及較長單位文字不再互相遮擋。
- 交付接口擴展為統一分析報告 renderer；state v3、telemetry v3 與 report schema v2 的 workflow1-only run 仍生成既有質控/組裝報告。
- 病毒分類 run 生成確定性的分類報告，包含適用的 reads 預處理摘要、候選數、聚類代表數、脊椎動物病毒候選數、代表性 contig 分類證據及真實 CSV/XLSX/FASTA 產物。
- 無候選結果時明確顯示「未檢出符合流程判定條件的候選」；分類欄位缺失時保留空值，不從其他證據推測，也不產生病因或臨床結論。

### 前端

- `/analysis` 僅在管理員查看成功或失敗終態 run 時顯示「下载内部技术报告」。
- 新增報告 Blob 下載 API、下載中狀態與錯誤提示；成功與失敗 run 均可下載內部技術報告。
- 成功 workflow1 或病毒分類 run 的狀態接口對所有已驗證使用者提供 `report_available`，右側任務區是唯一的「下载诊断意见书」入口；分析卡片沿用線性 steps，不顯示底層 workflow 邊界或並行分支。

### 新對話回覆與標題排程

- 新分析對話不再於主回覆前建立未註冊的 title-generation task，避免同一 BioAgent 並行初始化兩個 Claude SDK client，導致首次 assistant 僅留下空白 placeholder。
- `title_generation` 保留在主 completion 的 background task 集合中，待 assistant 完成並持久化後再使用完整 user/assistant 上下文生成標題；既有 fallback、API payload 與前端資料結構維持不變。
- 新增 handler 級回歸測試，確認開啟或關閉自動標題時設定均完整交給主 completion，且新對話只建立一個主 task。

### 分支 commits

- `dcfe31a57 :bug: prevent BioAgent chat submit during IME composition`
- `01c030c11 :sparkles: add admin internal technical reports for analysis runs`
- `8fc723985 :sparkles: add deterministic analysis report delivery`

## `agent` 改動

### 分析方案契約

- state v3 的 `execution_spec` 支援 `workflow1` 與 `virus_classification`；前者以 `entry_rule`、`exit_rule` 描述連續區段，後者以 typed input 與 `viral_type` 描述完整病毒分類。
- run 輸入不再固定為 `read1/read2` 頂層欄位；每種 typed input 的 `data` 結構由 workflow adapter 驗證，因此後續可擴展 contigs、reference、表格等輸入。
- `steps[].rules` 必須與 adapter 計算出的區段完全一致；缺少 `execution_spec`、未知 adapter、未知輸入型別、相對路徑、反向區段或不一致 rules 的方案不得執行。
- plan revision 會完整保存新的 `execution_spec`；execute prompt 僅注入固定 runner 的單一命令。
- `virus_classification` 接受 `raw_paired_reads` 或 `contigs_fasta`；未指定搜索範圍時固定為 RNA+DNA，明確要求時可選 RNA 或 DNA。

### Workflow adapter

- 新增 workflow adapter registry，由 adapter 集中負責 workflow source、rule 順序、入口所需輸入型別、run-local 配置、輸入物化及終點 targets。
- workflow1 的線性 DAG 為 `fastp → bowtie2 → merge → megahit → rename_filter`，允許選擇其中任意連續區段。
- workflow1 支援 `fastp/raw_paired_reads`、`bowtie2/fastp_paired_reads`、`merge/clean_paired_reads`、`megahit/merged_paired_reads` 與 `rename_filter/contigs_fasta` 五種入口。
- 從中途 rule 開始時，adapter 會將既有輸入以 run-local symlink 物化到 workflow 預期的 prerequisite 路徑，建立必要的 ancillary placeholder，並以明確 targets 保證不重跑先前 rules。
- 病毒分類固定使用 `workflow2_virusid_2026db`。reads 輸入建立上游與分類兩個 phase，將 ≥1 kb contigs 直接交給分類 phase 並避免重複改名；contigs 輸入只建立分類 phase。
- 因 reads 的上游 contigs 已帶樣本前綴，其「序列預處理」保存並執行 `get_orfs`、`merge_orfs`、`merge_contigs`；直接 contigs 的同一線性節點另包含實際執行的 `rename_contigs`。
- 分類卡片固定為線性階段：序列預處理、病毒候選搜索、候選序列提取、分類證據分析與結果匯總；聚類、CheckV 及多資料庫比對的實際並行關係不作為 UI 分支。

### 固定 runner 與 telemetry

- `analysis_runner.py` CLI 僅接受 `--state <state_path>`；runner 從 state 選擇 adapter，自行複製 workflow、生成 samples/config、物化輸入並建立 targets。
- 固定使用 Snakemake 9.23.1、8 cores、run-local source cache、`--printshellcmds` 與 `--benchmark-extended`。
- agent 不再準備 workflow 檔案、不再直接拼接 Snakemake 命令，也不再手工更新終態 state；gatekeeper 僅允許原樣執行 runtime 注入的 runner 命令。
- runner 對 workflow 準備、輸入驗證、成功、失敗、取消與部分輸出統一寫入終態 state、execution log、telemetry、benchmark JSONL、manifest 與報告可用狀態。
- runner 依序執行 adapter 準備的 phase；每個 phase 使用獨立 workflow、results、log、benchmark 與 source cache，任一 phase 失敗或取消後不啟動後續 phase。
- 每個 job 記錄 rule、wildcards、開始與結束時間、wall time、CPU time、平均有效核心、最大 RSS/VMS/USS/PSS、I/O、threads、輸入大小、資源、完整命令及軟體版本；敏感 token、密鑰與環境值會統一遮罩。
- 自動收集原始輸入與各階段 seqkit extended stats，解析 Fastp JSON、去 rRNA 比對率、組裝與最終過濾指標，並按方案 rules 聚合為 step，同時保留 job 級明細。
- 新增 workflow1 交付資料 schema，按 sample 聚合多個 run/lane，保存 S0–S4 結構化指標、外部中途輸入語義與各階段狀態；Bowtie2 摘要按 run 獨立保存。
- runner 在成功終態標記交付報告可用，失敗或取消終態標記不可用；runtime 不再接收 AI `diagnostic_report` 控制塊，也不發送報告 output item，下載完全由 Open WebUI 的 run 狀態驅動。
- workflow2 的 run-local 副本為全部 rules 注入 extended benchmark，並讓既有 pandas 匯總步驟額外輸出候選、聚類代表及脊椎動物候選 CSV；runner 以標準庫解析後寫入分類 telemetry。

### 問題修復與實際恢復

- 分類失敗 run `analysis-20260730-165639-db7516fd` 在 DNA HMM 第一輪得到零命中；這是合法的空分析結果，但原迭代腳本仍嘗試以 pandas 讀取只有 HMMER 註解的 `domtblout`，因而拋出 `EmptyDataError`。
- runner 現在只修改 workflow2 的 run-local 副本：任一輪零命中或沒有序列通過 motif coverage 時，該搜索通道正常結束並補齊剩餘輪次的空 `domtblout`，使 RNA、DNA 任一通道為空時仍可由既有彙整器繼續處理；共享 workflow2 原始目錄與搜索閾值均不變。
- 最新分類失敗 run `analysis-20260730-163502-245f2eb4` 顯示 workflow2 的迭代 HMM 腳本無法從子程序 `PATH` 找到 `seqkit`；runner 現在將配置的 `seqkit` 所在目錄加入每個 Snakemake phase 的環境，使同一環境內的 HMMER、CD-HIT 與 TaxonKit 亦可被腳本解析。
- Snakemake 對極短 job 可能在 benchmark JSONL 寫入字串 `"NA"`；runner 會在解析邊界規範化為 `null`，避免資源聚合再次拋錯，並保留 workflow 的真實失敗終態與完整 telemetry。
- 原失敗 run `analysis-20260728-110859-be8853a3` 的原因是舊執行路徑假設 workflow 已由 agent 預先準備，但 run 中只有 `.bioagent/`，導致 Snakemake 找不到 `workflow/rules/upstream.smk`。
- 新 runner 將 workflow 準備納入確定性執行流程，消除對 agent 手工複製與配置 workflow 的依賴。
- 已在原 Open WebUI 對話建立新 run `analysis-20260728-120606-9453ee29`，以 `raw_paired_reads` 執行 `fastp → bowtie2 → merge`，三個 job 全部成功，returncode 為 0。
- 實際 run 共處理 5,536,168 reads，Fastp 後保留 4,285,442 reads，保留率為 77.41%，去 rRNA 比對率為 0.02%；telemetry、benchmark、12 個輸出檔案與內部技術報告資料均已就緒，舊失敗 run 保留不變。

### 串流 Markdown 回合邊界

- runtime 依 Claude SDK `message_start` 保存 assistant 回合邊界；前一回合已有可見文字時，在下一回合第一個 `text_delta` 前補足 Markdown 所需的兩個換行。
- 邊界計算會扣除前段結尾與新段開頭既有的換行；同一 assistant 回合內的多個 delta 原樣串接，沒有前置文字的工具回合不產生開頭空行。
- 持久聊天與 ephemeral/background task 共用同一正規化器，正規化後才交給 `analysis_plan` filter，因此跨 delta、跨 assistant 回合的控制塊仍不會洩漏。
- streaming 與 non-streaming adapter 均合併為相同文字，工具後的 `##` 標題可以穩定渲染為 Markdown 標題。

### 分支 commits

- `487421b :sparkles: add typed workflow segments and deterministic analysis runner`
- `e126c7b :sparkles: add deterministic workflow1 execution reporting`

## 驗證結果

- Agent 單元測試共 69 項通過，覆蓋 typed input、所有 workflow1 入口、reads/contigs 病毒分類、RNA/DNA/RNA+DNA、phase 串接與兩階段失敗短路、run-local instrumentation、分類 CSV、phase-tagged job 輸入輸出與命令、workflow 工具 PATH、`"NA"` benchmark、空 HMM 搜索、成功、失敗、取消、state 原子更新、報告可用狀態及聊天串流回合邊界。
- Open WebUI 後端相關單元測試共 33 項通過，覆蓋管理員權限、chat/run 驗證、路徑逃逸、state/telemetry/report 新 schema、成功與失敗報告、分類結果與空結果、HTML escaping、workflow1 圖表、結構化串流持久化及新對話標題 task 排程。
- 前端 analysis 結構化 output Vitest 共 7 項通過；本次修改的 TypeScript/Svelte 檔案 Prettier check 通過。
- Agent 本次修改檔案及 Open WebUI 新增回歸測試的 Ruff format/check 通過；`main.py` 全檔檢查仍只有既有 lint 債務，所有 repo 的 `git diff --check` 通過。
- Snakemake 9.23.1 已解析 instrumented workflow1；真實 `workflow2_virusid_2026db` 使用範例 contigs 與 RNA+DNA dry-run 成功解析 21 個 jobs，包含雙 HMM 搜索、聚類、CheckV、多資料庫比對及匯總，return code 為 0。
- 使用失敗 run 的真實 ORF、RdRp HMM 與修正後的工具 `PATH` 完成 5 輪 iterative HMM smoke test，`seqkit`、HMMER 與 CD-HIT 均可解析，return code 為 0。
- 使用 run `analysis-20260730-165639-db7516fd` 的真實 ORF 與 DNA marker HMM 重現零命中；修正後通道 return code 為 0、五輪 `domtblout` target 齊全，coverage 彙整器在 DNA-only 模式輸出零候選 CSV，並在 RNA+DNA 模式保留該 run 的一個 RNA 候選。
- 真實三步恢復 run 已成功完成，並使用真實 DB 對話、state 與 telemetry 驗證自包含技術報告可以正確渲染。
- 真實 run `analysis-20260728-145014-792b62d7` 已驗證新交付報告顯示 `5.54 M reads`、`0.83 Gb`、fastp 保留率 `77.41%`、rRNA 比對率 `0.02%`，未執行的 merge/assembly 顯示占位說明。
- 隔離的新分析對話 smoke test 已驗證第一條訊息即可得到非空回覆，assistant 正常完成、持久 transcript 只包含一份 user request，標題在主回覆後更新；測試使用的 DB、Claude state 與 runs 均已刪除。
- Node 22 前端 production build 成功；本次未啟動前端，隔離測試使用的後端與 agent 已停止，完成後不留下相關服務。

## 後續更新方式

後續在此分支增加功能時，應更新上方 submodule commit、在相應 submodule 章節補充設計與行為變更、更新測試數量及實際驗證結果，並在需要時新增「後續邊界」說明。本文檔只記錄本分支相對各 submodule 基準分支的有效改動，不複製完整程式碼或逐檔案羅列機械性修改。
