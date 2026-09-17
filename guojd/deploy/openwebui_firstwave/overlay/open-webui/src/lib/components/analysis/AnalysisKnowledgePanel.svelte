<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		annotateAnalysisGenome,
		classifyAnalysisSequence,
		getAnalysisKnowledgeHealth,
		queryAnalysisKnowledge
	} from '$lib/apis/analysis';
	import Spinner from '$lib/components/common/Spinner.svelte';

	const DEFAULT_FASTA =
		'/data/user/guojindan/Projects/XvirMind/testdata/contigs/KP641127.fna';

	let familyQuery = 'Flaviviridae';
	let fastaPath = DEFAULT_FASTA;
	let busy = false;
	let health: Record<string, any> | null = null;
	let result: Record<string, any> | null = null;
	let error = '';

	const token = () => localStorage.token as string;

	const show = (value: Record<string, any>) => {
		result = value;
		error = '';
	};

	const fail = (caught: unknown) => {
		error = caught instanceof Error ? caught.message : String(caught);
		toast.error(error);
	};

	const run = async (work: () => Promise<Record<string, any>>) => {
		if (busy) return;
		busy = true;
		error = '';
		try {
			show(await work());
		} catch (caught) {
			fail(caught);
		} finally {
			busy = false;
		}
	};

	const queryFamily = () =>
		run(() =>
			queryAnalysisKnowledge(token(), 'taxonomy_family_info', { family_name: familyQuery })
		);

	const searchKb = () =>
		run(() => queryAnalysisKnowledge(token(), 'taxonomy_search_kb', { query: familyQuery, limit: 8 }));

	const listRva = () =>
		run(() =>
			queryAnalysisKnowledge(token(), 'annotation_list_families', { query: familyQuery })
		);

	const classify = (confirm: boolean) =>
		run(() =>
			classifyAnalysisSequence(token(), {
				genome: fastaPath,
				family: familyQuery || undefined,
				confirm
			})
		);

	const annotate = (confirm: boolean) =>
		run(() =>
			annotateAnalysisGenome(token(), {
				genome: fastaPath,
				family: familyQuery || undefined,
				confirm
			})
		);

	onMount(async () => {
		try {
			health = await getAnalysisKnowledgeHealth(token());
		} catch (caught) {
			health = { error: caught instanceof Error ? caught.message : String(caught) };
		}
	});
</script>

<section class="knowledge-panel" aria-label="知识查询与专项计算">
	<div class="section-heading">
		<h3>知识与专项</h3>
		<span>查询不跑计算；定种 / RVA 需确认</span>
	</div>
	<p class="hint">
		定种：wangdaxi virus_taxonomy（kb.jsonl）。注释增量：RVA。流程注释仍走 W6。
	</p>
	{#if health}
		<p class="health">
			分类 MCP：{health.taxonomy?.status ?? health.error ?? '未知'}　RVA MCP：{health.annotation?.status ??
				'未知'}
		</p>
	{/if}
	<label>
		科名 / 检索词
		<input bind:value={familyQuery} placeholder="Flaviviridae" />
	</label>
	<div class="actions">
		<button type="button" disabled={busy} on:click={queryFamily}>查科级规则</button>
		<button type="button" disabled={busy} on:click={searchKb}>检索 kb.jsonl</button>
		<button type="button" disabled={busy} on:click={listRva}>查 RVA 覆盖</button>
	</div>
	<label>
		FASTA（确认后专项）
		<input bind:value={fastaPath} />
	</label>
	<div class="actions">
		<button type="button" disabled={busy} on:click={() => classify(false)}>定种 dry-run</button>
		<button type="button" class="confirm" disabled={busy} on:click={() => classify(true)}>确认定种</button>
		<button type="button" disabled={busy} on:click={() => annotate(false)}>RVA dry-run</button>
		<button type="button" class="confirm" disabled={busy} on:click={() => annotate(true)}>确认 RVA</button>
	</div>
	{#if busy}
		<p class="status"><Spinner className="size-4" /> 请求中…</p>
	{/if}
	{#if error}
		<p class="error">{error}</p>
	{/if}
	{#if result}
		<pre>{JSON.stringify(result.structuredContent ?? result, null, 2)}</pre>
	{/if}
</section>

<style>
	.knowledge-panel {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 10px 12px 16px;
	}
	.section-heading {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		align-items: baseline;
	}
	.section-heading h3 {
		margin: 0;
		font-size: 14px;
	}
	.section-heading span,
	.hint,
	.health,
	.status {
		color: rgba(203, 229, 241, 0.72);
		font-size: 12px;
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 12px;
		color: rgba(223, 244, 252, 0.82);
	}
	input {
		border: 1px solid rgba(100, 160, 196, 0.32);
		border-radius: 7px;
		background: rgba(8, 29, 47, 0.76);
		color: #dff5ff;
		padding: 6px 8px;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	button {
		border: 1px solid rgba(100, 160, 196, 0.32);
		border-radius: 7px;
		background: rgba(8, 29, 47, 0.76);
		color: #dff5ff;
		padding: 6px 9px;
		font-size: 12px;
	}
	button.confirm {
		border-color: rgba(36, 226, 244, 0.55);
		color: #24e2f4;
	}
	button:disabled {
		opacity: 0.45;
	}
	.error {
		color: #fca5a5;
		font-size: 12px;
	}
	pre {
		max-height: 360px;
		overflow: auto;
		margin: 0;
		border: 1px solid rgba(84, 131, 163, 0.28);
		border-radius: 8px;
		background: rgba(3, 15, 26, 0.58);
		padding: 8px;
		font-size: 11px;
		white-space: pre-wrap;
		word-break: break-word;
	}
</style>
