<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	import type { AnalysisArtifactContract, AnalysisDataset } from '$lib/apis/analysis';
	import Spinner from '$lib/components/common/Spinner.svelte';

	export let dataset: AnalysisDataset;
	export let catalog: AnalysisArtifactContract[] = [];
	export let saving = false;

	type DraftRecord = {
		record_id: string;
		run_id?: string;
		sample_id?: string;
		files: Record<string, string>;
	};
	type DraftArtifact = { id: string; type: string; records: DraftRecord[] };

	const dispatch = createEventDispatcher<{
		save: { artifacts: DraftArtifact[] };
		replan: void;
	}>();
	const STATUS_LABELS: Record<string, string> = {
		checking: '正在全量预检',
		needs_review: '需要确认',
		ready: '已就绪',
		invalid: '预检失败',
		stale: '文件已变化'
	};

	let editing = false;
	let selectedType = '';
	let draftArtifacts: DraftArtifact[] = [];
	let loadedKey = '';

	const contractFor = (type: string) => catalog.find((item) => item.type === type);
	const grouping = (artifact: AnalysisDataset['artifacts'][number]) =>
		artifact.records
			.map((record) => [record.sample_id, record.run_id].filter(Boolean).join(' / '))
			.filter(Boolean)
			.join('、');
	const availableTypes = () =>
		catalog.filter((item) => !draftArtifacts.some((artifact) => artifact.type === item.type));
	const newRecord = (type: string, index: number): DraftRecord => {
		const contract = contractFor(type);
		return {
			record_id: `rec-${index + 1}`,
			...(contract?.identity_fields.includes('run_id') ? { run_id: `run-${index + 1}` } : {}),
			...(contract?.identity_fields.includes('sample_id')
				? { sample_id: `sample-${index + 1}` }
				: {}),
			files: Object.fromEntries((contract?.roles ?? []).map((role) => [role.name, '']))
		};
	};
	const resetDraft = () => {
		draftArtifacts = dataset.artifacts.map((artifact) => ({
			id: artifact.id,
			type: artifact.type,
			records: artifact.records.map((record) => ({
				record_id: record.record_id,
				...(record.run_id ? { run_id: record.run_id } : {}),
				...(record.sample_id ? { sample_id: record.sample_id } : {}),
				files: Object.fromEntries(
					Object.entries(record.files).map(([role, source]) => [role, source.path])
				)
			}))
		}));
		selectedType = availableTypes()[0]?.type ?? '';
	};
	const addArtifact = () => {
		if (!selectedType) return;
		const next = draftArtifacts.length + 1;
		draftArtifacts = [
			...draftArtifacts,
			{ id: `input-${next}`, type: selectedType, records: [newRecord(selectedType, 0)] }
		];
		selectedType = availableTypes()[0]?.type ?? '';
	};
	const addRecord = (artifactIndex: number) => {
		const artifact = draftArtifacts[artifactIndex];
		artifact.records = [...artifact.records, newRecord(artifact.type, artifact.records.length)];
		draftArtifacts = [...draftArtifacts];
	};
	const removeRecord = (artifactIndex: number, recordIndex: number) => {
		draftArtifacts[artifactIndex].records.splice(recordIndex, 1);
		draftArtifacts = [...draftArtifacts];
	};
	const removeArtifact = (artifactIndex: number) => {
		draftArtifacts.splice(artifactIndex, 1);
		draftArtifacts = [...draftArtifacts];
		selectedType = availableTypes()[0]?.type ?? '';
	};
	const sourceOptions = (kind: 'file' | 'directory') =>
		dataset.sources.filter((source) => source.kind === kind);
	const pathUsedElsewhere = (
		path: string,
		artifactIndex: number,
		recordIndex: number,
		roleName: string
	) =>
		draftArtifacts.some((artifact, currentArtifactIndex) =>
			artifact.records.some((record, currentRecordIndex) =>
				Object.entries(record.files).some(
					([role, value]) =>
						value === path &&
						(currentArtifactIndex !== artifactIndex ||
							currentRecordIndex !== recordIndex ||
							role !== roleName)
				)
			)
		);
	const validDraft = () => {
		const ids = draftArtifacts.map((artifact) => artifact.id.trim());
		const paths = draftArtifacts.flatMap((artifact) =>
			artifact.records.flatMap((record) => Object.values(record.files))
		);
		return (
			draftArtifacts.length > 0 &&
			ids.every((id) => /^[A-Za-z0-9_.-]+$/.test(id)) &&
			new Set(ids).size === ids.length &&
			draftArtifacts.every((artifact) => {
				const contract = contractFor(artifact.type);
				return (
					contract &&
					artifact.records.length > 0 &&
					artifact.records.every(
						(record) =>
							/^[A-Za-z0-9_.-]+$/.test(record.record_id) &&
							contract.identity_fields.every((field) =>
								/^[A-Za-z0-9_.-]+$/.test(record[field] ?? '')
							)
					)
				);
			}) &&
			paths.every(Boolean) &&
			new Set(paths).size === paths.length
		);
	};
	const save = () => dispatch('save', { artifacts: draftArtifacts });

	$: datasetKey = `${dataset.dataset_id}:${dataset.revision}`;
	$: if (datasetKey !== loadedKey) {
		loadedKey = datasetKey;
		editing = false;
		resetDraft();
	}
</script>

<section class="dataset-card" aria-label="当前数据集">
	<header>
		<div>
			<strong>Dataset r{dataset.revision}</strong>
			<span class:ready={dataset.status === 'ready'}>{STATUS_LABELS[dataset.status]}</span>
		</div>
		<small>{dataset.check_version}</small>
	</header>

	<div class="dataset-summary">
		<span>{dataset.sources.length} 个路径</span>
		<span
			>{dataset.artifacts.reduce((count, item) => count + item.records.length, 0)} 个 records</span
		>
		{#if dataset.checks?.full?.record_count !== undefined}
			<span>已检查 {dataset.checks.full.record_count} pairs</span>
		{/if}
	</div>

	{#if dataset.status === 'checking'}
		<p class="notice"><Spinner className="size-3.5" /> 正在后台锁步扫描完整 FASTQ</p>
	{/if}
	{#if dataset.issues.length}
		<ul class="issues">
			{#each dataset.issues as item}
				<li><code>{item.code}</code><span>{item.message}</span></li>
			{/each}
		</ul>
	{/if}

	{#if editing}
		<div class="editor">
			{#each draftArtifacts as artifact, artifactIndex}
				{@const contract = contractFor(artifact.type)}
				<div class="artifact">
					<div class="artifact-heading">
						<strong>{contract?.label ?? artifact.type}</strong>
						<input aria-label="Artifact ID" bind:value={artifact.id} />
						<button type="button" on:click={() => removeArtifact(artifactIndex)}>移除</button>
					</div>
					{#each artifact.records as record, recordIndex}
						<div class="record">
							<label>record_id<input bind:value={record.record_id} /></label>
							{#each contract?.identity_fields ?? [] as field}
								<label>{field}<input bind:value={record[field]} /></label>
							{/each}
							{#each contract?.roles ?? [] as role}
								<label
									>{role.name}
									<select bind:value={record.files[role.name]}>
										<option value="">选择路径</option>
										{#each sourceOptions(role.kind) as source}
											<option
												value={source.path}
												disabled={pathUsedElsewhere(
													source.path,
													artifactIndex,
													recordIndex,
													role.name
												)}>{source.path}</option
											>
										{/each}
									</select>
								</label>
							{/each}
							{#if artifact.records.length > 1}
								<button type="button" on:click={() => removeRecord(artifactIndex, recordIndex)}
									>删除 record</button
								>
							{/if}
						</div>
					{/each}
					{#if contract?.collection}
						<button type="button" on:click={() => addRecord(artifactIndex)}>添加 record</button>
					{/if}
				</div>
			{/each}
			<div class="add-row">
				<select bind:value={selectedType}>
					{#each availableTypes() as item}<option value={item.type}>{item.label}</option>{/each}
				</select>
				<button type="button" disabled={!selectedType} on:click={addArtifact}>添加 artifact</button>
			</div>
			<div class="actions">
				<button type="button" on:click={() => (editing = false)}>取消</button>
				<button class="primary" type="button" disabled={saving || !validDraft()} on:click={save}>
					{saving ? '保存中…' : '保存新 revision'}
				</button>
			</div>
		</div>
	{:else}
		<div class="artifact-list">
			{#each dataset.artifacts as artifact}
				<div>
					<strong>{contractFor(artifact.type)?.label ?? artifact.type}</strong>
					<span>{grouping(artifact) || `${artifact.records.length} records`}</span>
				</div>
			{/each}
		</div>
		<div class="actions">
			{#if dataset.actions.can_edit}
				<button type="button" on:click={() => (editing = true)}>修订配对与角色</button>
			{/if}
			{#if dataset.status === 'ready'}
				<button class="primary" type="button" on:click={() => dispatch('replan')}
					>按此数据集生成方案</button
				>
			{/if}
		</div>
	{/if}
</section>

<style>
	.dataset-card {
		border: 1px solid rgba(63, 183, 205, 0.35);
		border-radius: 8px;
		background: rgba(5, 22, 35, 0.78);
		padding: 10px;
		color: #d8edf4;
	}
	header,
	header > div,
	.dataset-summary,
	.actions,
	.add-row,
	.artifact-heading {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	header {
		justify-content: space-between;
	}
	header span {
		color: #f7bb61;
		font-size: 11px;
	}
	header span.ready {
		color: #4fe0a4;
	}
	header small {
		color: #7195a5;
	}
	.dataset-summary {
		margin-top: 8px;
		color: #8fb0be;
		font-size: 12px;
	}
	.notice {
		display: flex;
		align-items: center;
		gap: 6px;
		color: #70dce9;
		font-size: 12px;
	}
	.issues {
		display: grid;
		gap: 5px;
		margin: 8px 0;
		padding: 0;
		list-style: none;
		font-size: 11px;
	}
	.issues li {
		display: grid;
		gap: 2px;
	}
	.issues code {
		color: #f7bb61;
	}
	.artifact-list {
		display: grid;
		gap: 5px;
		margin-top: 8px;
	}
	.artifact-list div {
		display: flex;
		justify-content: space-between;
		font-size: 12px;
	}
	.editor {
		display: grid;
		gap: 10px;
		max-height: min(52vh, 520px);
		margin-top: 10px;
		overflow-y: auto;
		padding-right: 2px;
	}
	.artifact {
		display: grid;
		gap: 7px;
		border-top: 1px solid rgba(110, 160, 180, 0.2);
		padding-top: 8px;
	}
	.artifact-heading input {
		min-width: 0;
		flex: 1;
	}
	.record {
		display: grid;
		gap: 6px;
		padding: 7px;
		background: rgba(8, 31, 46, 0.8);
	}
	label {
		display: grid;
		gap: 3px;
		color: #8fb0be;
		font-size: 10px;
	}
	input,
	select {
		min-width: 0;
		border: 1px solid rgba(100, 158, 181, 0.3);
		border-radius: 5px;
		background: #071a28;
		padding: 5px;
		color: #d8edf4;
		font-size: 11px;
	}
	button {
		border: 1px solid rgba(101, 166, 190, 0.35);
		border-radius: 5px;
		padding: 5px 8px;
		color: #b8d4df;
		font-size: 11px;
	}
	button.primary {
		border-color: #25bfd3;
		color: #54e5f1;
	}
	button:disabled {
		opacity: 0.4;
	}
	.actions {
		justify-content: flex-end;
		margin-top: 9px;
	}
</style>
