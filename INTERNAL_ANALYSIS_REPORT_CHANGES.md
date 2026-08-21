# `feat/internal-analysis-report` 分支變更記錄

本文檔記錄主 repo 的 `feat/internal-analysis-report` 分支中 `open-webui` 與 `agent` 兩個 submodule 的整體改動，作為後續開發、測試、審查與合併時的持續更新記錄。新增功能或調整既有設計時，應直接在相應章節追加或修訂內容，並同步更新 submodule commit 與驗證結果。

> 2026-08-21 更新：Workflow 1–6 已統一為 `analysis_pipeline` v2。本文較早章節保留 `workflow1`、`virus_classification`、`adaptive_virus_analysis`、線性 steps 與 report schema v2 的演進背景；若與下方「Workflow 1–6 通用分析 Pipeline」章節衝突，以新版章節為準。新版不接受舊 adapter，也不保證舊 run state 可重新展示。

## Submodule 版本

| Submodule    | 分支                            | 基準分支 | 目前 commit |
| ------------ | ------------------------------- | -------- | ----------- |
| `open-webui` | `feat/internal-analysis-report` | `bgi`    | `8fc723985` |
| `agent`      | `feat/internal-analysis-report` | `main`   | `e126c7b`   |

## `open-webui` 改動

### Workflow 1–6 通用分析 Pipeline

- 後端分析狀態與報告白名單統一為 `workflow_id="analysis_pipeline"`、delivery report `kind="analysis_pipeline"` 與 schema v3；舊 adapter、舊 report kind 和不匹配 state 不再進入新版展示與下載流程。
- `/analysis` 的結構化方案型別新增 `depends_on`、`produces` 與 `is_deliverable`。前端依 DAG 深度排列階段，同層並排顯示宿主、微生物譜、病毒定量等分支，不再把所有公開階段誤畫成單一直線，且可同時標示多個交付終點。
- 路由資料改為明確保存 `requested_mode`、`effective_mode`、`adaptive`、適用性原因、deadline、抽樣比例、可用路徑與 `short_circuit_scope="pipeline"`。沒有可用雙端 reads 時，`auto`／`emergency` 在 UI 顯示「当前输入不适用快速初筛，直接执行」；`deep` 仍不可執行。
- `standard` 不插入初篩；`auto` 高置信可跳過整個多分支 pipeline、低置信繼續完整流程；`emergency` 初篩後一律終止並由 run state 將全部規劃階段標記為 skipped。
- 診斷報告 renderer 保留既有上游與病毒分類專用版面；其他單分支、中間結果或多分支方案使用通用 pipeline 報告，統一展示階段狀態、實際耗時、有效 CPU、峰值記憶體、各分析域指標與輸出 manifest。
- 通用報告可遞迴展開宿主樣本／鑑定數、微生物各層級 taxa 數與每個樣本 top taxon、病毒定量樣本／reference／有效記錄／最高 RPM，以及病毒注釋序列數、策略分布、功能注釋數與一致性 warning 數；所有動態內容仍經 HTML escaping。
- 前端方案解析不再接受缺少新版 routing metadata 的歷史方案直接確認，路由設定仍以最新結構化方案優先，修改模式或 deadline 後必須重新生成方案。

### 對話輸入與 IME

- 修復 BioAgent 聊天輸入框在中文、日文等輸入法仍處於 composition 階段時按下 Enter 會意外提交訊息的問題。
- 分析檔案樹提交的伺服器檔案以 `server_path` metadata 保存路徑、大小、修改時間及 `analysis_file_tree` 來源，使技術報告可以區分檔案選擇器、一般附件與聊天文字中的手動路徑。

### 分析 run 狀態與管理員接口

- 分析 run 狀態對管理員增加內部技術報告是否可用的資訊，一般使用者不會取得該欄位。
- 新增管理員限定的 `GET /analysis/runs/internal-report` endpoint，嚴格驗證 run root、state 中的 chat 關聯及 telemetry 版本，拒絕路徑逃逸、chat/run 不匹配與舊 state。
- 保持既有診斷意見書 endpoint 與一般使用者流程不變，原始 telemetry JSON 僅保存在 run 的 `.bioagent/` 目錄。

### 內部技術報告

- 後端以 DB 對話、run state 與 telemetry 確定性組合自包含 HTML 報告，不使用 agent 撰寫報告；舊 run 若已有 agent trace 仍可作為歷史資料讀取，新 run 不再產生該檔案。
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

### 歷史資源估算卡片與啟動判定

- `/analysis` 資源卡片改用版本化結構資料，分三欄顯示耗時 P50/P90/建議預留、峰值記憶體 P50/P90/建議容量與核心數，以及可信度、匹配 run 數、不同輸入規模數和資料不足警告。
- 前端分開解析核心 `analysis_plan` 與可選的 `resource_estimate`；資源資料缺失或格式無效時顯示「暂不可估」，不會丟棄有效方案或停用啟動按鈕。
- 啟動判定只依賴是否為最新方案、`ready_to_execute` 與是否仍在生成；`resource_estimate.status="insufficient"`、零匹配樣本或校準器失敗均不影響有效方案啟動。
- 無法執行的方案可攜帶 `blocking_reason`，最新方案會在停用的啟動按鈕旁直接顯示真實原因，避免把 execution spec 驗證失敗誤認為硬體資源不足。

### 自適應路由介面與原子啟動

- `/analysis` 頂部新增「智能／緊急／標準／深度」路由選擇器；深度模式標示為暫未開放，緊急模式可設定目標時限，方案卡固定展示 `5% 快速初筛 → 自适应路由决策` 及各模式的後續路徑。
- 路由設定以 `chat_meta.analysis_routing` 持久化；載入舊對話時以最新結構化方案的 routing 優先恢復控制器，修改模式或時限會使舊方案失效，必須套用設定並重新生成。
- 確認按鈕以單一請求攜帶 `analysis_mode=execute`，不再先發送隱藏 `/execute` 或輪詢等待；前端使用本地 `confirming` 鎖避免快速雙擊建立重複執行請求，提交後回到規劃模式。
- BioAgent 請求只白名單轉發 `analysis_mode`、`analysis_routing` 與 `source`，其他 chat metadata 不會傳給模型；既有對話每次請求仍合併保存最新 routing。
- 原始雙端 reads 的病毒分類方案只有在規範化為 `adaptive_virus_analysis` 且 routing 與 UI 一致時才能確認；純 workflow1 與 contigs 分類不會被強制轉換。

### 路由狀態、阻斷與報告交付

- `/analysis/runs/status` 可同時返回 routing 決策與 `blocked` 終態，前端顯示初篩階段、模式、最終路徑、置信度、資源阻斷及目標時限是否達成。
- 路徑 B 因資源不足而阻斷時保留已完成的初篩結果，並允許下載低置信初篩報告；`execution.status=blocked` 與 `report.available=true` 可以同時成立。
- 完整分類報告新增「自适应路由说明」，逐樣本顯示最高物種命中 reads、抽樣占比、病毒內占比的實際值、門檻與通過狀態，並確定性說明智能模式選擇路徑 A 或 B 的原因。
- 內部技術報告新增路由請求、最終路徑、reason codes、逐樣本置信檢查、資源准入快照與歷史估算摘要；快速預警與快速初篩報告共用相同門檻解釋。
- 報告下載時會從逐 job 時間重新計算既有 telemetry 的階段時間，因此不改寫歷史 run 也能修正跨午夜時把 `Thu...`、`Fri...` 直接按字串比較所造成的起止顛倒。
- 階段時間欄位區分實際「階段歷時」與「Job 耗時合計」，平均有效核心以 CPU 時間除以實際階段歷時計算；逐 job 時間、CPU、RSS、分類證據及整體 run 耗時不因舊聚合錯誤而重算。

### 新對話回覆與標題排程

- 新分析對話不再於主回覆前建立未註冊的 title-generation task，避免同一 BioAgent 並行初始化兩個 Claude SDK client，導致首次 assistant 僅留下空白 placeholder。
- `title_generation` 保留在主 completion 的 background task 集合中，待 assistant 完成並持久化後再使用完整 user/assistant 上下文生成標題；既有 fallback、API payload 與前端資料結構維持不變。
- 新增 handler 級回歸測試，確認開啟或關閉自動標題時設定均完整交給主 completion，且新對話只建立一個主 task。

### 非同步執行終態交付與中斷恢復

- 後端向 BioAgent 轉送 `X-OpenWebUI-Message-Id`；agent 回傳 `analysis_run` 結構化 output item 後，後端以 run state 為唯一終態來源註冊背景監看，不要求瀏覽器或原 SSE 連線持續存在。
- `analysis_run` 固定包含 `run_id`、`run_dir`、`state_path` 與 `log_path`。state 到達 `completed`、`failed` 或 `blocked` 時，後端確定性生成簡潔摘要，更新同一則 assistant message 的 `content`、`output` 與 `done=true`，再發送 socket completion。
- 後端啟動時掃描 `BIOAGENT_RUN_ROOT`，恢復帶有 assistant message 關聯的 run monitor；沒有可恢復 run 的舊 `done=false` assistant placeholder 會終態化為「响应已中断，请重试。」。
- provider 非串流錯誤、串流錯誤及 task cancellation 均會把可見錯誤與 `done=true` 雙寫至 chat JSON 和 `chat_message`，避免輸入動畫永久停留。
- 保留既有分析狀態面板與五秒輪詢，沒有增加新的前端元件；短命 runner 測試覆蓋「立即啟動回覆 → 背景終態 → 同一訊息自動更新」。

### 歷史對話資料修復

- 使用 SQLite online backup API 建立 `webui.db.backup-20260819-163325` 一致性備份後，精確修復最新三個空白 assistant placeholder，保留所有 chat、run 與 build 產物。
- chat `97292566-0767-4f97-9399-af91f2dbd8c2` 的最後 assistant message 已依 `analysis-20260813-160906-0f9eda85` 完成 state 更新為確定性成功摘要及 `analysis_run=completed`。
- 四則修復訊息均驗證 chat JSON 與 `chat_message` 的文字及 `done=true` 一致，資料庫 `integrity_check` 通過。

### 分支 commits

- `dcfe31a57 :bug: prevent BioAgent chat submit during IME composition`
- `01c030c11 :sparkles: add admin internal technical reports for analysis runs`
- `8fc723985 :sparkles: add deterministic analysis report delivery`

## `agent` 改動

### Workflow 1–6 通用分析 Pipeline

- 對外 execution spec 收斂為唯一的 `analysis_pipeline` v2；移除 `workflow1`、`virus_classification` 與 `adaptive_virus_analysis` 三種舊 adapter 的執行入口。模型只描述 typed `inputs`、`deliverables`、`options.viral_type` 與 `policy.mode`，不再手寫 `entry_rule`、`exit_rule`、`steps` 或精確 rules。
- 新增靜態 workflow/artifact registry，集中定義 27 個公開生物學階段、artifact 必需檔案角色、記錄粒度、sample/run identity、階段輸入輸出、Snakemake rules 與源 workflow。所有外部檔案路徑必須為絕對路徑，重複 input ID、重複 artifact type、重複記錄、sample 集合不一致、缺失角色、未使用輸入與非法交付物均在建 run 前拒絕。
- runtime 從外部 artifact 與一個或多個交付物確定性編譯最小依賴閉包，輸出規範化 `steps`，每步包含 `id`、`label`、`rules`、`depends_on`、產物型別與交付標記。共享上游只編譯一次，病毒 RNA、DNA、RNA+DNA 選擇只改變受控 catalog 中的搜索 rules。
- 公開階段覆蓋上游 `read_qc` 至 `contig_filter`、病毒識別 `virus_sequence_prep` 至 `virus_summary`、宿主識別 `host_mapping` 至 `host_summary`、微生物譜 `microbe_classify` 至 `microbe_summary`、病毒定量 `virus_read_mapping` 至 `virus_rpm`，以及病毒注釋 `virus_quality` 至 `annotation_delivery`。
- 每套源 workflow 最多建立一個 run-local phase；同一 workflow 的多個交付物合併 targets 聯集，跨 workflow 依 DAG 拓撲順序執行並直接引用上游產物。中間 artifact bundle 會物化至各 workflow 預期路徑，只為 Snakemake 必需但沒有生物學意義的伴隨檔建立 placeholder，不偽造核心分析資料。
- 新增 workflow 3–6 的 source 設定、run-local config rewrite、輸入準備、顯式 target 選擇與 benchmark instrumentation；源 workflow 目錄保持唯讀且不被修改。Workflow 6 的 taxonomy TSV 始終是獨立 `virus_taxonomy` 輸入，不從 workflow 2 結果推測生成。
- 主要跨流程連接包含 clean reads 至組裝、宿主 mapping、Kraken/Bracken 與病毒定量；filtered/direct contigs 至病毒識別或宿主 BLAST；病毒候選／識別序列至定量 reference 或注釋輸入。raw reads 可一次編譯病毒識別、宿主、微生物譜與病毒定量的多分支閉包。
- 路由由規範化 spec 統一驅動：`standard` 直接執行；`auto`／`emergency` 僅在實際依賴閉包使用 paired-read artifact 時插入 5% Kraken2 初篩；沒有 paired reads 時 `effective_mode` 降級為 `standard`；自適應短路範圍固定為整個 pipeline。
- 資源校準改用編譯後的階段簽名、各 workflow 資料庫簽名與多輸入規模；同一 run 的總時長按 phase 相加，峰值記憶體與 CPU 取各 phase 最大值，歷史不足時明確返回不可校準而不阻止有效方案。
- delivery report 統一為 schema v3 `analysis_pipeline`，在保留上游與病毒分類既有結構的同時，新增宿主、微生物譜、病毒定量與病毒注釋的確定性結果解析。runtime、system prompt、README、architecture 與 workflow gatekeeper 均已切換至新版契約。

### 分析方案契約

- state v3 的 `execution_spec` 支援 `workflow1` 與 `virus_classification`；前者以 `entry_rule`、`exit_rule` 描述連續區段，後者以 typed input 與 `viral_type` 描述完整病毒分類。
- run 輸入不再固定為 `read1/read2` 頂層欄位；每種 typed input 的 `data` 結構由 workflow adapter 驗證，因此後續可擴展 contigs、reference、表格等輸入。
- `steps[].rules` 必須與 adapter 計算出的區段完全一致；缺少 `execution_spec`、未知 adapter、未知輸入型別、相對路徑、反向區段或不一致 rules 的方案不得執行。
- plan revision 會完整保存新的 `execution_spec`；確認執行後由 runtime 直接消費已驗證方案，不再建立 Claude execute prompt。
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
- agent 不再準備 workflow 檔案、不再透過 Claude Bash 工具執行或直接拼接 Snakemake 命令，也不再手工更新 runner 終態 state；runtime 只負責原子建立初始 state 並啟動固定 runner subprocess。
- runner 對 workflow 準備、輸入驗證、成功、失敗、取消與部分輸出統一寫入終態 state、execution log、telemetry、benchmark JSONL、manifest 與報告可用狀態。
- runner 依序執行 adapter 準備的 phase；每個 phase 使用獨立 workflow、results、log、benchmark 與 source cache，任一 phase 失敗或取消後不啟動後續 phase。
- 每個 job 記錄 rule、wildcards、開始與結束時間、wall time、CPU time、平均有效核心、最大 RSS/VMS/USS/PSS、I/O、threads、輸入大小、資源、完整命令及軟體版本；敏感 token、密鑰與環境值會統一遮罩。
- 自動收集原始輸入與各階段 seqkit extended stats，解析 Fastp JSON、去 rRNA 比對率、組裝與最終過濾指標，並按方案 rules 聚合為 step，同時保留 job 級明細。
- 新增 workflow1 交付資料 schema，按 sample 聚合多個 run/lane，保存 S0–S4 結構化指標、外部中途輸入語義與各階段狀態；Bowtie2 摘要按 run 獨立保存。
- runner 在成功終態標記交付報告可用，失敗或取消終態標記不可用；runtime 不再接收 AI `diagnostic_report` 控制塊，也不發送報告 output item，下載完全由 Open WebUI 的 run 狀態驅動。
- workflow2 的 run-local 副本為全部 rules 注入 extended benchmark，並讓既有 pandas 匯總步驟額外輸出候選、聚類代表及脊椎動物候選 CSV；runner 以標準庫解析後寫入分類 telemetry。

### 歷史 Telemetry 資源校準

- 新增 `.claude/sessions/bioagent/resource-history.sqlite3` SQLite 索引，以 WAL、`run_id` 唯一鍵與增量 mtime 檢查回填既有 v2/v3 telemetry；每個 terminal run 自動 upsert，成功、失敗與取消狀態均保留供稽核，但只有成功且資源欄位完整的 run 參與估算。
- `input_stats` 以路徑雜湊、檔案大小及 mtime 快取 `seqkit stats` 的 sequences/bases，不保存原始輸入路徑；後續規劃不再逐次掃描與重算所有歷史 run。
- 候選 run 嚴格匹配相同有序 rule 區段、typed input、RNA/DNA 範圍與資料庫指紋，並要求 reads/bases 或 contig/bases 均在 0.5–2 倍範圍內；按最大對數比例距離選取最近 20 筆，優先使用相同 `0`、`1`、`2+` 並行負載資料。
- 耗時及記憶體 P50 使用中位數、P90 使用 nearest-rank empirical quantile；高、中、低可信度分別保留 10%、15%、25% 安全餘量，舊 telemetry、未知負載或樣本規模不足時固定降為低可信度。
- 完全沒有匹配資料時不外推 P50/P90，僅提供 8 GiB 一般上游、24 GiB MEGAHIT、128 GiB 病毒分類的保守記憶體下限及 runner 的 8 核配置，因此新流程第一次執行不會被歷史資料缺口阻擋。
- runtime 會丟棄模型提供的資源數字，在 execution spec 驗證後加入確定性估算；若資源校準本身異常，僅省略估算，不改變有效方案的 `ready_to_execute`。
- runner 每秒彙總 Snakemake process tree RSS、整機記憶體與其他 analysis runner 數量；telemetry v3 保存 run 級峰值與負載桶，實績記憶體取 process-tree 峰值和 benchmark 最大值的較大者，不保存冗長時間序列。
- workflow1 plan 若遺漏 `entry_rule` 或 `exit_rule`，runtime 只在 `steps[].rules` 可唯一對應一個非空連續區段時補全；顯式衝突、不連續 rules 或輸入類型不匹配仍拒絕執行並輸出 `blocking_reason`。System prompt 與 gatekeeper 亦明確禁止將分類專用的 `viral_type` 寫入 workflow1 spec。

### 自適應病毒分析與路由決策

- 新增 `adaptive_virus_analysis` adapter：對每個樣本以固定隨機種子抽取 5% 成對 reads，校驗 R1/R2 數量與 read ID，執行輕量 fastp、去 rRNA 與 `Viral_20260226` Kraken2 快速初篩。
- 每個樣本必須同時滿足最高物種命中至少 1,000 reads、占抽樣 read pairs 至少 1%、占病毒 reads 至少 80% 才屬高置信；多樣本任務要求全部樣本通過。
- `auto` 在高置信時選擇路徑 A 快速預警，低置信時選擇路徑 B 完整分類；`standard` 固定進入 B；`emergency` 無論置信度均在初篩後直接產生報告，不自動升級完整流程；`deep` 本期不可執行。
- 快速初篩為每個樣本保存三項 `confidence_checks`、門檻快照、實際值、通過狀態與失敗原因碼；`.bioagent/state.json`、`routing.json` 與 telemetry 同步記錄決策、資源、歷史、實際耗時、deadline 結果及終態，`accuracy` 與 `expert_feedback` 暫留空值。
- UI 提供 routing 且模型產生 `virus_classification + raw_paired_reads` 時，runtime 確定性升級為 adaptive spec，補上快速初篩與路由決策步驟並以 UI routing 覆蓋模型設定；既有 adaptive 方案只更新 routing。
- `analysis_mode=execute` 在同一請求內直接消費最新方案，不建立或查詢 Claude session；run 建立前檢查同一方案是否已執行，重複確認只返回既有狀態，不覆寫 state 或重跑。

### Runtime 直啟動與冪等執行

- execute 請求驗證 `ready_to_execute`、`execution_spec` 與 `steps[].rules` 後，原子建立 state，保存 Open WebUI assistant message ID，並以獨立 session subprocess 啟動 `analysis_runner.py`；SSE 立即返回啟動文字與 `analysis_run` item。
- runner 在進程入口自行寫入 PID，避免短命流程已完成後被父進程以舊 running state 覆寫；獨立 reaper 負責回收 subprocess，但後端關閉不會終止仍在執行的分析。
- 同一方案的重複確認會讀取並返回既有 state；舊 state 若缺少 assistant message ID，可在不重啟 runner 的前提下補上當前關聯。
- `Popen` 啟動錯誤會立即把 state 寫成 failed 並返回可見錯誤；runner 入口未預期例外亦會補寫 failed、return code、錯誤與完成時間，避免 state 永久停留在 running。
- 移除不再使用的 Claude execute prompt、Bash tool trace recorder，以及「Claude 回合結束即把 runner 判定為失敗」的舊邏輯；方案模式與 Claude 對話 session 行為維持不變。

### 資源准入與時間 telemetry

- 初篩前要求 CPU 低於 85%、至少 4 個可用執行緒及 4 GiB 可用記憶體；只有選擇路徑 B 時才再次檢查完整流程資源，不排隊、不拆批、不自動降級。
- 有可靠歷史校準時採用校準後 reserve；沒有同規模歷史或估算狀態不足時，raw reads 完整流程以 8 個執行緒及 24 GiB 可用記憶體作為最低准入，不再因固定 128 GiB 估算超過實體記憶體而永久阻斷。
- Snakemake 日誌中的本地時間在解析邊界轉為帶時區的 ISO 8601，階段起止以時間值而非星期字串聚合，並同步寫回 state steps。
- telemetry 的 `wall_seconds` 表示最早開始至最晚結束的實際階段歷時，`job_wall_seconds` 表示 benchmark job 耗時合計，`effective_cores` 改以實際階段歷時計算，避免並行 job 被誤報為串行耗時。

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

### 2026-08-21 Workflow 1–6 Pipeline 驗證

- Agent 全量單元測試 96 項通過，涵蓋 artifact schema、絕對路徑、重複 ID、sample 對齊、每個公開階段的外部入口與終點、最小 DAG、多分支閉包、路由降級／短路、資源校準、runner、telemetry 與通用報告。
- Workflow 1–6 均以真實源 workflow 建立臨時 run-local phase 並完成 Snakemake dry-run；涵蓋 raw reads 上游中間結果、direct contigs 病毒識別、clean reads 宿主＋微生物雙交付、reads＋virus reference 定量、workflow 2 候選＋reads 定量、病毒 FASTA＋taxonomy TSV 注釋，以及 raw reads 多分支閉包。
- Open WebUI 後端 analysis／report 單元測試 35 項通過，包含通用、多分支、病毒分類、初篩、blocked、manifest、深層指標展開、資源欄位、HTML escaping 與報告下載邊界。
- 前端 Vitest 全量 20 項通過，其中 analysis plan 19 項覆蓋 DAG 分支分層、路由時效性、舊方案失效、緊急 deadline、原子確認與 skipped／交付狀態；相關 TypeScript／Svelte 檔案通過 Prettier check。
- Agent 與本次後端修改檔通過 Ruff，兩個 submodule 均通過 `git diff --check`。使用既有 Pyodide 靜態資源直接執行 Vite production build 成功；標準 `npm run build` 的 Pyodide 聯網預下載因沙箱代理不可達而未完成，與本次前端編譯無關，驗證副作用已還原且未清理 build 產物。

- Agent 完整單元測試共 99 項通過；除既有 Kraken2、路由、資源、telemetry 與報告覆蓋外，新增驗證 execute 不呼叫 Claude、runner 僅啟動一次、重試冪等、PID 與 message ID 寫入、啟動錯誤終態化，以及短命 subprocess 的立即回覆與背景完成。
- Open WebUI 相關單元測試共 46 項通過；除既有 analysis metadata、路由與報告覆蓋外，新增驗證 message-id header、completed／failed／blocked 摘要、同一訊息 output 更新與 socket 通知、後端重啟恢復及舊 placeholder 修復。
- 前端 analysis 結構化 output Vitest 共 18 項通過，覆蓋模式選擇、緊急目標時限、最新方案 routing 恢復、設定失效與重新生成、單次原子確認、雙擊鎖及 adaptive 方案確認條件；相關 TypeScript/Svelte 檔案通過 Prettier check。
- Agent 本次修改檔案及 Open WebUI 新增模組與回歸測試的 Ruff check 通過；Open WebUI 大型既有檔案的全量 Ruff 仍有 163 項存量 lint 債務，所有 repo 的 `git diff --check` 通過。
- Snakemake 9.23.1 已解析 instrumented workflow1；真實 `workflow2_virusid_2026db` 使用範例 contigs 與 RNA+DNA dry-run 成功解析 21 個 jobs，包含雙 HMM 搜索、聚類、CheckV、多資料庫比對及匯總，return code 為 0。
- 使用失敗 run 的真實 ORF、RdRp HMM 與修正後的工具 `PATH` 完成 5 輪 iterative HMM smoke test，`seqkit`、HMMER 與 CD-HIT 均可解析，return code 為 0。
- 使用 run `analysis-20260730-165639-db7516fd` 的真實 ORF 與 DNA marker HMM 重現零命中；修正後通道 return code 為 0、五輪 `domtblout` target 齊全，coverage 彙整器在 DNA-only 模式輸出零候選 CSV，並在 RNA+DNA 模式保留該 run 的一個 RNA 候選。
- 真實三步恢復 run 已成功完成，並使用真實 DB 對話、state 與 telemetry 驗證自包含技術報告可以正確渲染。
- 真實 run `analysis-20260728-145014-792b62d7` 已驗證新交付報告顯示 `5.54 M reads`、`0.83 Gb`、fastp 保留率 `77.41%`、rRNA 比對率 `0.02%`，未執行的 merge/assembly 顯示占位說明。
- 真實 adaptive run `analysis-20260813-160906-0f9eda85` 的既有 state/telemetry 未被改寫；動態分類報告已驗證顯示 `811 / ≥ 1,000`、`0.0746% / ≥ 1%`、`96.55% / ≥ 80%` 及選擇路徑 B 的原因，內部報告將「分類證據分析」修正為 `2026-08-13 16:45:01` 至 `2026-08-14 04:57:01`，並分列 43,920 秒階段歷時與 43,931.49 秒 Job 合計。
- 隔離的新分析對話 smoke test 已驗證第一條訊息即可得到非空回覆，assistant 正常完成、持久 transcript 只包含一份 user request，標題在主回覆後更新；測試使用的 DB、Claude state 與 runs 均已刪除。
- Node 22 高記憶體前端 production build 成功，完整輸出保存在 `/tmp/bioagent-open-webui-build-20260819.log`；本次未改動前端源碼，沒有新增 Prettier 或 Vitest 範圍，也未啟動前端、後端或 agent。

## 後續更新方式

後續在此分支增加功能時，應更新上方 submodule commit、在相應 submodule 章節補充設計與行為變更、更新測試數量及實際驗證結果，並在需要時新增「後續邊界」說明。本文檔只記錄本分支相對各 submodule 基準分支的有效改動，不複製完整程式碼或逐檔案羅列機械性修改。
