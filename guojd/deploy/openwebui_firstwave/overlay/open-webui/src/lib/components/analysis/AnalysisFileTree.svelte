<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { listAnalysisFiles, type AnalysisFileEntry } from '$lib/apis/analysis';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';
	import Clipboard from '$lib/components/icons/Clipboard.svelte';
	import Document from '$lib/components/icons/Document.svelte';
	import Folder from '$lib/components/icons/Folder.svelte';
	import FolderOpen from '$lib/components/icons/FolderOpen.svelte';
	import Refresh from '$lib/components/icons/Refresh.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';

	export let selectedPaths: string[] = [];

	type DirectoryState = {
		entries: AnalysisFileEntry[];
		loaded: boolean;
		loading: boolean;
		error: string;
		nextCursor: number | null;
	};

	type VisibleRow = {
		entry: AnalysisFileEntry;
		depth: number;
	};

	const dispatch = createEventDispatcher<{
		apply: { paths: string[]; files: AnalysisFileEntry[] };
	}>();

	const PAGE_SIZE = 100;
	const createEmptyDirectoryState = (): DirectoryState => ({
		entries: [],
		loaded: false,
		loading: false,
		error: '',
		nextCursor: null
	});

	let root = '读取中';
	let directoryStates = new Map<string, DirectoryState>();
	let expandedPaths = new Set<string>();
	let rootState: DirectoryState = createEmptyDirectoryState();
	let visibleRows: VisibleRow[] = [];
	let selectedPathSet = new Set<string>();
	let selectedDataSize = '0 B';

	const getErrorMessage = (error: unknown) =>
		error instanceof Error ? error.message : '无法读取分析文件';

	const formatSize = (size: number) => {
		if (size < 1024) return `${size} B`;

		const units = ['KB', 'MB', 'GB', 'TB'];
		let value = size / 1024;
		let unit = units[0];

		for (let index = 1; index < units.length && value >= 1024; index += 1) {
			value /= 1024;
			unit = units[index];
		}

		return `${value.toFixed(value >= 10 ? 0 : 1)} ${unit}`;
	};

	const setDirectoryState = (path: string, state: DirectoryState) => {
		directoryStates.set(path, state);
		directoryStates = new Map(directoryStates);
	};

	const getDirectoryState = (path: string): DirectoryState =>
		directoryStates.get(path) ?? createEmptyDirectoryState();

	const loadDirectory = async (path = '/', reset = false) => {
		const current = getDirectoryState(path);
		if (current.loading) return;
		if (current.loaded && !reset && current.nextCursor === null) return;

		const cursor = reset ? 0 : (current.nextCursor ?? 0);
		setDirectoryState(path, { ...current, loading: true, error: '' });

		try {
			const response = await listAnalysisFiles(localStorage.token, path, cursor, PAGE_SIZE);
			root = response.root;
			setDirectoryState(path, {
				entries: reset ? response.entries : [...current.entries, ...response.entries],
				loaded: true,
				loading: false,
				error: '',
				nextCursor: response.next_cursor ?? null
			});
		} catch (error) {
			setDirectoryState(path, {
				...current,
				loading: false,
				error: getErrorMessage(error)
			});
		}
	};

	const buildRows = (path = '/', depth = 0): VisibleRow[] => {
		const state = getDirectoryState(path);
		const rows: VisibleRow[] = [];

		for (const entry of state.entries) {
			rows.push({ entry, depth });

			if (entry.type === 'directory' && expandedPaths.has(entry.path)) {
				rows.push(...buildRows(entry.path, depth + 1));
			}
		}

		return rows;
	};

	const collectCachedEntries = () => {
		const entries = new Map<string, AnalysisFileEntry>();
		for (const state of directoryStates.values()) {
			for (const entry of state.entries) {
				entries.set(entry.abs_path, entry);
			}
		}
		return [...entries.values()];
	};

	const toggleDirectory = async (entry: AnalysisFileEntry) => {
		if (entry.type !== 'directory') return;

		if (expandedPaths.has(entry.path)) {
			expandedPaths.delete(entry.path);
			expandedPaths = new Set(expandedPaths);
			return;
		}

		expandedPaths.add(entry.path);
		expandedPaths = new Set(expandedPaths);

		if (!getDirectoryState(entry.path).loaded) {
			await loadDirectory(entry.path, true);
		}
	};

	const toggleSelection = (entry: AnalysisFileEntry) => {
		selectedPaths = selectedPathSet.has(entry.abs_path)
			? selectedPaths.filter((path) => path !== entry.abs_path)
			: [...selectedPaths, entry.abs_path];
	};

	const clearSelection = () => {
		selectedPaths = [];
	};

	const refreshRoot = async () => {
		directoryStates = new Map();
		expandedPaths = new Set();
		await loadDirectory('/', true);
	};

	const refreshDirectory = async (path: string) => {
		await loadDirectory(path, true);
	};

	const applySelection = () => {
		if (selectedPaths.length === 0) return;
		const selected = new Set(selectedPaths);
		dispatch('apply', {
			paths: selectedPaths,
			files: collectCachedEntries().filter((entry) => selected.has(entry.abs_path))
		});
	};

	const copySelection = async () => {
		if (selectedPaths.length === 0) return;

		try {
			await navigator.clipboard.writeText(selectedPaths.join('\n'));
			toast.success('已复制路径');
		} catch {
			toast.error('复制失败');
		}
	};

	const rowClick = (entry: AnalysisFileEntry) => {
		if (entry.type === 'directory') {
			void toggleDirectory(entry);
		} else {
			toggleSelection(entry);
		}
	};

	const rowKeydown = (event: KeyboardEvent, entry: AnalysisFileEntry) => {
		if (event.key !== 'Enter' && event.key !== ' ') return;

		event.preventDefault();
		rowClick(entry);
	};

	onMount(() => {
		void loadDirectory('/', true);
	});

	$: selectedPathSet = new Set(selectedPaths);
	$: {
		directoryStates;
		selectedPaths;
		selectedDataSize = formatSize(
			collectCachedEntries().reduce(
				(total, entry) =>
					total +
					(selectedPaths.includes(entry.abs_path) && entry.type === 'file' ? (entry.size ?? 0) : 0),
				0
			)
		);
	}
	$: {
		directoryStates;
		rootState = getDirectoryState('/');
	}
	$: {
		directoryStates;
		expandedPaths;
		visibleRows = buildRows();
	}
</script>

<div class="file-tree-shell">
	<div class="file-tree-toolbar">
		<div class="root-label" title={root}>{root}</div>
		<div class="tree-actions">
			<button
				type="button"
				class="small-action"
				on:click={applySelection}
				disabled={!selectedPaths.length}
			>
				创建数据集
			</button>
			<button
				type="button"
				class="small-action"
				on:click={copySelection}
				disabled={!selectedPaths.length}
			>
				<Clipboard className="size-3.5" strokeWidth="1.8" />
				复制
			</button>
			<button type="button" class="icon-action" aria-label="刷新文件列表" on:click={refreshRoot}>
				<Refresh className="size-4" strokeWidth="1.8" />
			</button>
			<button
				type="button"
				class="icon-action"
				aria-label="清空选择"
				disabled={!selectedPaths.length}
				on:click={clearSelection}
			>
				<XMark className="size-4" strokeWidth="1.8" />
			</button>
		</div>
	</div>
	<p class="file-hint">
		可选 1 对 FASTQ（单样本）或同时勾选多对（多样本，将得到多条 records，需确认 sample 分组）。也可选 1 条或多条 contig。测试包在 testdata/scenarios。勾选后必须点「确认选用并同步到对话」，文件才会进入中间方案。
	</p>
	<div class="selection-summary" aria-label="文件选择摘要">
		<span>
			<em>已选路径</em>
			<strong>{selectedPaths.length}</strong>
		</span>
		<span>
			<em>数据量</em>
			<strong>{selectedDataSize}</strong>
		</span>
	</div>

	<div class="tree-list" role="tree" aria-label="分析文件列表">
		{#if rootState.loading && !rootState.loaded}
			<div class="tree-state">
				<Spinner className="size-4" />
				<span>加载文件列表</span>
			</div>
		{:else if rootState.error}
			<div class="tree-state error">
				<span>{rootState.error}</span>
			</div>
		{:else if visibleRows.length === 0}
			<div class="tree-state">
				<span>暂无文件</span>
			</div>
		{:else}
			{#each visibleRows as row (row.entry.abs_path)}
				{@const entry = row.entry}
				{@const directoryState = getDirectoryState(entry.path)}
				<div class="tree-row-wrap">
					<div
						class:selected={selectedPathSet.has(entry.abs_path)}
						class="tree-row"
						style={`--depth: ${row.depth}`}
						role="treeitem"
						tabindex="0"
						aria-expanded={entry.type === 'directory' ? expandedPaths.has(entry.path) : undefined}
						on:click={() => rowClick(entry)}
						on:keydown={(event) => rowKeydown(event, entry)}
					>
						<span class="tree-indent"></span>
						<span class="tree-chevron">
							{#if entry.type === 'directory'}
								{#if directoryState.loading}
									<Spinner className="size-3.5" />
								{:else if expandedPaths.has(entry.path)}
									<ChevronDown className="size-4" strokeWidth="1.9" />
								{:else}
									<ChevronRight className="size-4" strokeWidth="1.9" />
								{/if}
							{/if}
						</span>
						<input
							type="checkbox"
							checked={selectedPathSet.has(entry.abs_path)}
							aria-label={`选择 ${entry.name}`}
							on:click|stopPropagation={() => toggleSelection(entry)}
							on:keydown|stopPropagation={() => {}}
						/>
						<span class="tree-icon">
							{#if entry.type === 'directory'}
								{#if expandedPaths.has(entry.path)}
									<FolderOpen className="size-4" strokeWidth="1.75" />
								{:else}
									<Folder className="size-4" strokeWidth="1.75" />
								{/if}
							{:else}
								<Document className="size-4" strokeWidth="1.75" />
							{/if}
						</span>
						<span class="tree-name" title={entry.abs_path}>{entry.name}</span>
						{#if entry.type === 'file' && entry.size}
							<span class="tree-size">{formatSize(entry.size)}</span>
						{/if}
					</div>

					{#if entry.type === 'directory' && expandedPaths.has(entry.path)}
						{#if directoryState.error}
							<div class="tree-inline-state" style={`--depth: ${row.depth + 1}`}>
								<span>{directoryState.error}</span>
								<button type="button" on:click={() => refreshDirectory(entry.path)}>重试</button>
							</div>
						{:else if directoryState.nextCursor !== null}
							<div class="tree-inline-state" style={`--depth: ${row.depth + 1}`}>
								<button type="button" on:click={() => loadDirectory(entry.path)}>加载更多</button>
							</div>
						{/if}
					{/if}
				</div>
			{/each}

			{#if getDirectoryState('/').nextCursor !== null}
				<div class="tree-inline-state root-load-more">
					<button type="button" on:click={() => loadDirectory('/')}>加载更多</button>
				</div>
			{/if}
		{/if}
	</div>
</div>

<style>
	.file-tree-shell {
		display: flex;
		min-height: 0;
		flex: 1;
		flex-direction: column;
		overflow: hidden;
		border: 1px solid rgba(84, 131, 163, 0.28);
		border-radius: 8px;
		background: rgba(3, 15, 26, 0.58);
	}

	.file-tree-toolbar {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 8px;
		align-items: center;
		border-bottom: 1px solid rgba(101, 153, 187, 0.18);
		padding: 8px;
	}

	.file-hint {
		margin: 0;
		padding: 6px 10px 0;
		color: rgba(203, 229, 241, 0.7);
		font-size: 11px;
		line-height: 1.45;
	}

	.selection-summary {
		display: flex;
		align-items: center;
		gap: 8px;
		border-bottom: 1px solid rgba(101, 153, 187, 0.14);
		background: rgba(7, 25, 40, 0.52);
		padding: 6px 8px;
	}

	.selection-summary span {
		min-width: 0;
		display: inline-flex;
		align-items: baseline;
		gap: 6px;
		border: 1px solid rgba(93, 154, 190, 0.2);
		border-radius: 999px;
		background: rgba(9, 32, 50, 0.72);
		padding: 3px 9px;
		line-height: 1.2;
	}

	.selection-summary em {
		color: rgba(203, 229, 241, 0.64);
		font-size: 11px;
		font-style: normal;
		white-space: nowrap;
	}

	.selection-summary strong {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		color: #24e2f4;
		font-size: 12px;
		white-space: nowrap;
	}

	.root-label {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: rgba(223, 244, 252, 0.78);
		font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
		font-size: 12px;
	}

	.tree-actions {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.small-action,
	.icon-action,
	.tree-inline-state button {
		border: 1px solid rgba(100, 160, 196, 0.32);
		border-radius: 7px;
		background: rgba(8, 29, 47, 0.76);
		color: #dff5ff;
	}

	.small-action {
		height: 30px;
		display: inline-flex;
		align-items: center;
		gap: 5px;
		padding: 0 9px;
		font-size: 12px;
	}

	.icon-action {
		width: 30px;
		height: 30px;
		display: grid;
		place-items: center;
	}

	.small-action:disabled,
	.icon-action:disabled {
		cursor: not-allowed;
		opacity: 0.46;
	}

	.tree-list {
		min-height: 0;
		flex: 1;
		overflow: auto;
		padding: 5px 0;
	}

	.tree-row {
		--row-indent: calc(var(--depth) * 16px);
		width: 100%;
		height: 28px;
		display: grid;
		grid-template-columns: var(--row-indent) 18px 18px 18px minmax(0, 1fr) auto;
		gap: 4px;
		align-items: center;
		border: 0;
		background: transparent;
		color: rgba(226, 242, 249, 0.82);
		padding: 0 8px 0 6px;
		text-align: left;
	}

	.tree-row:hover,
	.tree-row.selected {
		background: rgba(41, 112, 150, 0.34);
		color: #f2fbff;
	}

	.tree-chevron,
	.tree-icon {
		display: grid;
		place-items: center;
		color: rgba(168, 207, 227, 0.82);
	}

	.tree-row input {
		width: 14px;
		height: 14px;
		accent-color: #25d8ef;
	}

	.tree-name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 13px;
	}

	.tree-size {
		color: rgba(195, 220, 232, 0.58);
		font-size: 11px;
	}

	.tree-state,
	.tree-inline-state {
		display: flex;
		align-items: center;
		gap: 8px;
		color: rgba(210, 235, 246, 0.62);
		font-size: 12px;
	}

	.tree-state {
		justify-content: center;
		min-height: 120px;
		padding: 16px;
		text-align: center;
	}

	.tree-state.error {
		color: #ffd4d4;
	}

	.tree-inline-state {
		margin-left: calc(var(--depth) * 16px + 46px);
		min-height: 28px;
	}

	.tree-inline-state button {
		height: 24px;
		padding: 0 8px;
		font-size: 12px;
	}

	.root-load-more {
		margin-left: 28px;
	}
</style>
