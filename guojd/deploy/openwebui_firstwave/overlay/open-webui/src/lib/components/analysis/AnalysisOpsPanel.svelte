<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		completeAnalysisUpload,
		enqueueAnalysisJob,
		evaluateAnalysisRules,
		getAnalysisOpsSnapshot,
		initAnalysisUpload,
		pauseAnalysisJob,
		putAnalysisUploadChunk,
		recoverAnalysisJob,
		submitAnalysisReview
	} from '$lib/apis/analysis';
	import Spinner from '$lib/components/common/Spinner.svelte';

	let snapshot: Record<string, any> | null = null;
	let busy = false;
	let error = '';
	let memberUser = '';
	let memberRole = 'viewer';
	let reviewReason = '证据不足，打回补齐 kb locator。';
	let fileInput: HTMLInputElement;

	const token = () => localStorage.token as string;

	const load = async () => {
		busy = true;
		error = '';
		try {
			snapshot = await getAnalysisOpsSnapshot(token());
		} catch (caught) {
			error = caught instanceof Error ? caught.message : String(caught);
		} finally {
			busy = false;
		}
	};

	const act = async (work: () => Promise<unknown>) => {
		busy = true;
		try {
			await work();
			await load();
		} catch (caught) {
			const message = caught instanceof Error ? caught.message : String(caught);
			error = message;
			toast.error(message);
		} finally {
			busy = false;
		}
	};

	const enqueueFirstWave = () =>
		act(async () => {
			for (const kind of ['workflow1', 'workflow2', 'workflow3', 'workflow4', 'workflow6']) {
				await enqueueAnalysisJob(token(), { kind, priority: kind === 'workflow1' ? 'high' : 'standard' });
			}
		});

	const uploadSelected = async () => {
		const file = fileInput?.files?.[0];
		if (!file) return;
		await act(async () => {
			const init = await initAnalysisUpload(token(), { filename: file.name, size: file.size });
			const chunkSize = init.chunk_size || 4 * 1024 * 1024;
			let index = 0;
			for (let offset = 0; offset < file.size; offset += chunkSize) {
				await putAnalysisUploadChunk(token(), init.id, index, file.slice(offset, offset + chunkSize));
				index += 1;
			}
			await completeAnalysisUpload(token(), init.id);
			toast.success(`已上传到 testdata/uploads/${file.name}`);
		});
	};

	onMount(load);
</script>

<section class="ops-panel">
	<div class="section-heading">
		<h3>第二波治理</h3>
		<button type="button" disabled={busy} on:click={load}>刷新</button>
	</div>
	{#if busy}<p><Spinner className="size-4" /> 加载中</p>{/if}
	{#if error}<p class="error">{error}</p>{/if}
	{#if snapshot}
		<p class="hint">项目 testdata 窗口；上传写入 testdata/uploads；队列含 W1–W4+W6 时长估计。</p>
		<h4>成员</h4>
		<ul>
			{#each snapshot.projects?.projects ?? [] as project}
				{#each project.members as member}
					<li>{project.id} · {member.user} · {member.role}</li>
				{/each}
			{/each}
		</ul>
		<div class="row">
			<input bind:value={memberUser} placeholder="用户名" />
			<select bind:value={memberRole}>
				<option>owner</option>
				<option>analyst</option>
				<option>reviewer</option>
				<option>viewer</option>
			</select>
		</div>
		<h4>分块上传</h4>
		<input bind:this={fileInput} type="file" />
		<button type="button" disabled={busy} on:click={uploadSelected}>上传到 testdata</button>
		<h4>优先级队列</h4>
		<button type="button" disabled={busy} on:click={enqueueFirstWave}>入队 W1–W4+W6</button>
		<ul>
			{#each snapshot.jobs?.jobs ?? [] as job}
				<li>
					{job.kind} · {job.status} · {job.priority} · {job.estimate?.wall_min} min
					<button type="button" on:click={() => act(() => pauseAnalysisJob(token(), job.id))}>暂停</button>
					<button type="button" on:click={() => act(() => recoverAnalysisJob(token(), job.id))}>恢复</button>
				</li>
			{/each}
		</ul>
		<h4>RVA 实跑</h4>
		<p>{snapshot.rva_demo?.status} pid={snapshot.rva_demo?.pid ?? '—'} GPU={(snapshot.rva_demo?.gpu?.devices || []).join('; ') || '无'}</p>
		<h4>专家打回</h4>
		<textarea bind:value={reviewReason}></textarea>
		<button
			type="button"
			disabled={busy}
			on:click={() =>
				act(() =>
					submitAnalysisReview(token(), {
						run_id: 'demo-kp641127',
						decision: 'reject',
						reason: reviewReason
					})
				)}>打回</button
		>
		<button
			type="button"
			disabled={busy}
			on:click={() =>
				act(() =>
					evaluateAnalysisRules(token(), [
						{ id: 'demo', family: 'Coronaviridae', rva_family: 'Flaviviridae', evidence: [] }
					])
				)}>演示矛盾规则</button
		>
		{#if snapshot.reviews?.reviews?.length}
			<ul>
				{#each snapshot.reviews.reviews as review}
					<li>{review.decision} · {review.actor} · {review.reason}</li>
				{/each}
			</ul>
		{/if}
	{/if}
</section>

<style>
	.ops-panel { padding: 10px 12px 16px; display: flex; flex-direction: column; gap: 8px; }
	.section-heading, .row { display: flex; gap: 8px; align-items: center; justify-content: space-between; }
	h3, h4 { margin: 8px 0 0; }
	.hint, li, p { color: rgba(203, 229, 241, 0.78); font-size: 12px; }
	.error { color: #fca5a5; }
	input, select, textarea, button {
		border: 1px solid rgba(100, 160, 196, 0.32);
		border-radius: 7px;
		background: rgba(8, 29, 47, 0.76);
		color: #dff5ff;
		padding: 6px 8px;
		font-size: 12px;
	}
	textarea { min-height: 64px; }
	ul { padding-left: 16px; margin: 4px 0; }
</style>
