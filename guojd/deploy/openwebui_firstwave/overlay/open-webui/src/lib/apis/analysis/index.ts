import { WEBUI_API_BASE_URL } from '$lib/constants';

export type AnalysisFileEntry = {
	name: string;
	type: 'file' | 'directory';
	path: string;
	abs_path: string;
	size?: number | null;
	modified?: number | null;
	has_children: boolean;
};

export type AnalysisFilesResponse = {
	root: string;
	path: string;
	abs_path: string;
	entries: AnalysisFileEntry[];
	next_cursor?: number | null;
};

export type AnalysisDatasetFingerprint = {
	device: number;
	inode: number;
	size: number;
	mtime_ns: number;
};

export type AnalysisDatasetSource = {
	path: string;
	kind: 'file' | 'directory';
	fingerprint: AnalysisDatasetFingerprint;
};

export type AnalysisDatasetRecord = {
	record_id: string;
	run_id?: string;
	sample_id?: string;
	files: Record<string, AnalysisDatasetSource>;
};

export type AnalysisDatasetArtifact = {
	id: string;
	type: string;
	records: AnalysisDatasetRecord[];
};

export type AnalysisDataset = {
	dataset_id: string;
	revision: number;
	status: 'checking' | 'needs_review' | 'ready' | 'invalid' | 'stale';
	sources: AnalysisDatasetSource[];
	artifacts: AnalysisDatasetArtifact[];
	checks: Record<string, any>;
	issues: Array<{ code: string; message: string; [key: string]: any }>;
	check_version: string;
	created_at: number;
	updated_at: number;
	actions: { can_edit: boolean; can_plan: boolean; can_execute: boolean };
};

export type AnalysisArtifactContract = {
	type: string;
	label: string;
	roles: Array<{ name: string; kind: 'file' | 'directory' }>;
	identity_fields: Array<'run_id' | 'sample_id'>;
	collection: boolean;
};

export type AnalysisGoal =
	| 'contig_filter'
	| 'virus_summary'
	| 'host_summary'
	| 'microbe_summary'
	| 'virus_rpm'
	| 'annotation_delivery';

export type AnalysisViralType = 'RNA' | 'DNA' | 'RNA+DNA';
export type DeterministicRoutingMode = 'auto' | 'standard' | 'emergency';

export type DeterministicAnalysisPlan = {
	type: 'analysis_plan';
	id: string;
	revision: number;
	status: 'completed';
	title: string;
	summary: string;
	ready_to_execute: boolean;
	dataset: { id: string; revision: number; status: string };
	goals: AnalysisGoal[];
	options: { viral_type: AnalysisViralType };
	routing?: Record<string, any>;
	steps: Array<Record<string, any>>;
	resource_estimate?: Record<string, any> | null;
	blocking_reason?: string | null;
	planner_version: number;
	created_at: number;
	run?: { run_id: string; run_dir?: string; state_path?: string; log_path?: string };
	execution?: {
		status: string;
		run_id: string;
		run?: { run_id: string; run_dir?: string; state_path?: string; log_path?: string } | null;
		error?: string | null;
		confirmed_at: number;
	};
};

export type AnalysisPlanResponse = { chat_id: string; plan: DeterministicAnalysisPlan };

export type AnalysisPlanPatch = {
	goals?: AnalysisGoal[];
	viral_type?: AnalysisViralType;
};

export type AnalysisPlanProposal = {
	id: string;
	plan_id: string;
	chat_id: string;
	base_plan_revision: number;
	status: 'pending' | 'accepted' | 'rejected' | 'superseded';
	patch: AnalysisPlanPatch;
	citations: string[];
	model?: string | null;
	message_id?: string | null;
	created_at: number;
	decided_at?: number | null;
};

export type AnalysisHealth = {
	deterministic: { status: string };
	conversation_model: { id: string; status: string; provider?: string };
	knowledge: { status: string; provider?: string };
};

const ANALYSIS_ERROR_ACTIONS: Record<string, string> = {
	DATASET_STALE: '文件在预检后已变化，请重新建立数据集。',
	DATASET_NOT_READY: '请等待预检完成，或按数据集问题提示修订文件。',
	DATASET_REVISION_CONFLICT: '数据集已有新版本，请重新加载后再修改。',
	PLAN_REVISION_CONFLICT: '方案已有新版本，请重新加载当前对话后再操作。',
	PLAN_NOT_LATEST: '请重新加载并使用最新方案。',
	PLAN_ROUTING_OBSOLETE: '历史方案使用旧路由契约，请重新生成方案后再确认。',
	PROPOSAL_STALE: '提案基于旧方案，请重新加载并重新提出修改。',
	PROPOSAL_NOT_PENDING: '该提案已处理，请重新加载当前对话。',
	PATCH_PENDING: '请先接受或拒绝待确认的方案修改。',
	PLANNER_UNAVAILABLE: '无法连接 BioAgent 分析服务，请确认服务已启动后重试。',
	RUNNER_UNAVAILABLE: '执行服务暂时不可用，请稍后重试。'
};

export class AnalysisApiError extends Error {
	code?: string;
	field?: string;
	context: Record<string, unknown>;
	retryable: boolean;

	constructor(detail: any, fallback: string) {
		const code = typeof detail?.code === 'string' ? detail.code : undefined;
		super((code && ANALYSIS_ERROR_ACTIONS[code]) || detail?.message || fallback);
		this.name = 'AnalysisApiError';
		this.code = code;
		this.field = typeof detail?.field === 'string' ? detail.field : undefined;
		this.context = detail?.context && typeof detail.context === 'object' ? detail.context : {};
		this.retryable = detail?.retryable === true;
	}
}

const analysisJson = async <T>(res: Response, fallback: string): Promise<T> => {
	if (!res.ok) {
		const error = await res.json().catch(() => ({}));
		const detail = error?.detail;
		if (detail && typeof detail === 'object') throw new AnalysisApiError(detail, fallback);
		throw new Error(typeof detail === 'string' ? detail : fallback);
	}
	return res.json();
};

const analysisHeaders = (token: string, json = false) => ({
	Accept: 'application/json',
	authorization: `Bearer ${token}`,
	...(json ? { 'Content-Type': 'application/json' } : {})
});

export const getAnalysisDatasetCatalog = async (
	token: string
): Promise<{ check_version: string; artifacts: AnalysisArtifactContract[] }> =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/datasets/catalog`, {
			headers: analysisHeaders(token)
		}),
		'无法读取数据集类型'
	);

export const createAnalysisDataset = async (
	token: string,
	paths: string[]
): Promise<AnalysisDataset> =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/datasets`, {
			method: 'POST',
			headers: analysisHeaders(token, true),
			body: JSON.stringify({ paths })
		}),
		'无法创建数据集'
	);

export const getAnalysisDataset = async (
	token: string,
	datasetId: string,
	revision?: number
): Promise<AnalysisDataset> => {
	const query = revision ? `?revision=${revision}` : '';
	return analysisJson(
		await fetch(
			`${WEBUI_API_BASE_URL}/analysis/datasets/${encodeURIComponent(datasetId)}${query}`,
			{ headers: analysisHeaders(token) }
		),
		'无法读取数据集'
	);
};

export const reviseAnalysisDataset = async (
	token: string,
	datasetId: string,
	baseRevision: number,
	artifacts: Array<Record<string, any>>
): Promise<AnalysisDataset> =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/datasets/${encodeURIComponent(datasetId)}`, {
			method: 'PATCH',
			headers: analysisHeaders(token, true),
			body: JSON.stringify({ base_revision: baseRevision, artifacts })
		}),
		'无法修订数据集'
	);

export const createAnalysisPlan = async (
	token: string,
	request: {
		chat_id?: string;
		dataset: { id: string; revision: number };
		goals: AnalysisGoal[];
		options: { viral_type: AnalysisViralType };
		routing: { mode: DeterministicRoutingMode };
		base_plan_revision?: number;
	}
): Promise<AnalysisPlanResponse> =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/plans`, {
			method: 'POST',
			headers: analysisHeaders(token, true),
			body: JSON.stringify(request)
		}),
		'无法生成分析方案'
	);

export const getLatestAnalysisPlan = async (
	token: string,
	chatId: string
): Promise<AnalysisPlanResponse> =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/plans/${encodeURIComponent(chatId)}/latest`, {
			headers: analysisHeaders(token)
		}),
		'无法读取分析方案'
	);

export const executeAnalysisPlan = async (
	token: string,
	planId: string,
	revision: number
): Promise<AnalysisPlanResponse> =>
	analysisJson(
		await fetch(
			`${WEBUI_API_BASE_URL}/analysis/plans/${encodeURIComponent(planId)}/revisions/${revision}/execute`,
			{ method: 'POST', headers: analysisHeaders(token) }
		),
		'无法启动分析'
	);

export const getAnalysisHealth = async (token: string): Promise<AnalysisHealth> =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/health`, { headers: analysisHeaders(token) }),
		'无法读取分析服务状态'
	);

export const getPendingAnalysisProposal = async (
	token: string,
	chatId: string
): Promise<AnalysisPlanProposal | null> =>
	(
		await analysisJson<{ proposal: AnalysisPlanProposal | null }>(
			await fetch(
				`${WEBUI_API_BASE_URL}/analysis/plans/${encodeURIComponent(chatId)}/proposals/pending`,
				{ headers: analysisHeaders(token) }
			),
			'无法读取方案修改提案'
		)
	).proposal;

export const registerAnalysisProposal = async (
	token: string,
	chatId: string,
	request: {
		base_plan_revision: number;
		proposal_id?: string;
		patch: AnalysisPlanPatch;
		citations?: string[];
		model?: string;
		message_id?: string;
	}
): Promise<AnalysisPlanProposal> =>
	(
		await analysisJson<{ proposal: AnalysisPlanProposal }>(
			await fetch(`${WEBUI_API_BASE_URL}/analysis/plans/${encodeURIComponent(chatId)}/proposals`, {
				method: 'POST',
				headers: analysisHeaders(token, true),
				body: JSON.stringify(request)
			}),
			'无法登记方案修改提案'
		)
	).proposal;

export const rejectAnalysisProposal = async (
	token: string,
	proposalId: string
): Promise<AnalysisPlanProposal> =>
	(
		await analysisJson<{ proposal: AnalysisPlanProposal }>(
			await fetch(
				`${WEBUI_API_BASE_URL}/analysis/proposals/${encodeURIComponent(proposalId)}/reject`,
				{ method: 'POST', headers: analysisHeaders(token) }
			),
			'无法拒绝方案修改提案'
		)
	).proposal;

export const acceptAnalysisProposal = async (
	token: string,
	proposalId: string
): Promise<AnalysisPlanResponse & { proposal: AnalysisPlanProposal }> =>
	analysisJson(
		await fetch(
			`${WEBUI_API_BASE_URL}/analysis/proposals/${encodeURIComponent(proposalId)}/accept`,
			{ method: 'POST', headers: analysisHeaders(token) }
		),
		'无法接受方案修改提案'
	);

export type AnalysisRunTask = {
	id: string;
	sample: string;
	stage: string;
	progress: number;
	tone: 'cyan' | 'green' | 'amber' | 'red';
};

export type AnalysisRunStatusResponse = {
	run_id?: string | null;
	run_dir?: string | null;
	status: 'idle' | 'planned' | 'running' | 'done' | 'failed' | 'blocked' | string;
	current_rule?: string | null;
	completed_steps: number;
	total_steps: number;
	progress: number;
	updated_at?: number | null;
	error?: string | null;
	report_available: boolean;
	internal_report_available?: boolean;
	routing?: {
		phase?: string;
		actual_duration_seconds?: number | null;
		request?: { mode?: string };
		decision?: {
			selected_route?: 'A' | 'B' | null;
			confidence?: 'high' | 'low';
			report_kind?: string;
			reason_codes?: string[];
		};
		screening?: {
			known_virus_high_confidence?: boolean;
			samples?: Array<{
				sample_id?: string;
				top_species?: { name?: string; taxid?: string; reads?: number } | null;
			}>;
		};
	};
	tasks: AnalysisRunTask[];
};

export const listAnalysisFiles = async (
	token: string,
	path = '/',
	cursor = 0,
	limit = 100
): Promise<AnalysisFilesResponse> => {
	const searchParams = new URLSearchParams();
	searchParams.set('path', path);
	searchParams.set('cursor', String(cursor));
	searchParams.set('limit', String(limit));

	const res = await fetch(`${WEBUI_API_BASE_URL}/analysis/files?${searchParams.toString()}`, {
		headers: {
			Accept: 'application/json',
			authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const error = await res.json().catch(() => ({}));
		throw new Error(error?.detail ?? '无法读取分析文件');
	}

	return res.json();
};

export const getAnalysisRunStatus = async (
	token: string,
	options: { runId?: string | null; runDir?: string | null } = {}
): Promise<AnalysisRunStatusResponse> => {
	const searchParams = new URLSearchParams();
	if (options.runId) searchParams.set('run_id', options.runId);
	if (options.runDir) searchParams.set('run_dir', options.runDir);

	const query = searchParams.toString();
	const res = await fetch(`${WEBUI_API_BASE_URL}/analysis/runs/status${query ? `?${query}` : ''}`, {
		headers: {
			Accept: 'application/json',
			authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const error = await res.json().catch(() => ({}));
		throw new Error(error?.detail ?? '无法读取分析任务状态');
	}

	return res.json();
};

export const getDiagnosticReport = async (token: string, runDir: string): Promise<Blob> => {
	const searchParams = new URLSearchParams({ run_dir: runDir });
	const res = await fetch(`${WEBUI_API_BASE_URL}/analysis/runs/report?${searchParams.toString()}`, {
		headers: {
			Accept: 'text/html',
			authorization: `Bearer ${token}`
		}
	});

	if (!res.ok) {
		const error = await res.json().catch(() => ({}));
		throw new Error(error?.detail ?? '无法下载诊断意见书');
	}

	return res.blob();
};

export const getInternalTechnicalReport = async (
	token: string,
	chatId: string,
	runDir: string
): Promise<Blob> => {
	const searchParams = new URLSearchParams({ chat_id: chatId, run_dir: runDir });
	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analysis/runs/internal-report?${searchParams.toString()}`,
		{
			headers: {
				Accept: 'text/html',
				authorization: `Bearer ${token}`
			}
		}
	);

	if (!res.ok) {
		const error = await res.json().catch(() => ({}));
		throw new Error(error?.detail ?? '无法下载内部技术报告');
	}

	return res.blob();
};


export type AnalysisKnowledgeHealth = Record<string, { status?: string; error?: string; url?: string }>;

export const getAnalysisKnowledgeHealth = async (
	token: string
): Promise<AnalysisKnowledgeHealth> =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/knowledge/health`, {
			headers: analysisHeaders(token)
		}),
		'无法读取知识服务状态'
	);

export const queryAnalysisKnowledge = async (
	token: string,
	tool: string,
	arguments_: Record<string, any> = {}
): Promise<Record<string, any>> =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/knowledge/query`, {
			method: 'POST',
			headers: analysisHeaders(token, true),
			body: JSON.stringify({ tool, arguments: arguments_ })
		}),
		'知识查询失败'
	);

export const classifyAnalysisSequence = async (
	token: string,
	request: { genome: string; family?: string; confirm?: boolean }
): Promise<Record<string, any>> =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/knowledge/classify`, {
			method: 'POST',
			headers: analysisHeaders(token, true),
			body: JSON.stringify(request)
		}),
		'定种请求失败'
	);

export const annotateAnalysisGenome = async (
	token: string,
	request: { genome: string; family?: string; confirm?: boolean }
): Promise<Record<string, any>> =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/knowledge/annotate`, {
			method: 'POST',
			headers: analysisHeaders(token, true),
			body: JSON.stringify(request)
		}),
		'注释请求失败'
	);


export const getAnalysisOpsSnapshot = async (token: string) =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/ops/snapshot`, { headers: analysisHeaders(token) }),
		'无法读取治理快照'
	);

export const enqueueAnalysisJob = async (
	token: string,
	body: { project_id?: string; kind: string; priority?: string; payload?: Record<string, any> }
) =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/ops/jobs`, {
			method: 'POST',
			headers: analysisHeaders(token, true),
			body: JSON.stringify(body)
		}),
		'无法入队'
	);

export const recoverAnalysisJob = async (token: string, jobId: string) =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/ops/jobs/${encodeURIComponent(jobId)}/recover`, {
			method: 'POST',
			headers: analysisHeaders(token)
		}),
		'无法恢复任务'
	);

export const pauseAnalysisJob = async (token: string, jobId: string) =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/ops/jobs/${encodeURIComponent(jobId)}/pause`, {
			method: 'POST',
			headers: analysisHeaders(token)
		}),
		'无法暂停任务'
	);

export const evaluateAnalysisRules = async (token: string, candidates: Array<Record<string, any>>) =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/ops/rules/evaluate`, {
			method: 'POST',
			headers: analysisHeaders(token, true),
			body: JSON.stringify({ candidates })
		}),
		'规则评估失败'
	);

export const submitAnalysisReview = async (
	token: string,
	body: { project_id?: string; run_id: string; decision: string; reason?: string }
) =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/ops/reviews`, {
			method: 'POST',
			headers: analysisHeaders(token, true),
			body: JSON.stringify(body)
		}),
		'审核提交失败'
	);

export const initAnalysisUpload = async (
	token: string,
	body: { filename: string; size: number; project_id?: string; sha256?: string }
) =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/ops/uploads/init`, {
			method: 'POST',
			headers: analysisHeaders(token, true),
			body: JSON.stringify(body)
		}),
		'无法初始化上传'
	);

export const completeAnalysisUpload = async (token: string, uploadId: string) =>
	analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/ops/uploads/${encodeURIComponent(uploadId)}/complete`, {
			method: 'POST',
			headers: analysisHeaders(token)
		}),
		'无法完成上传'
	);

export const putAnalysisUploadChunk = async (
	token: string,
	uploadId: string,
	index: number,
	blob: Blob
) => {
	const form = new FormData();
	form.append('index', String(index));
	form.append('file', blob);
	return analysisJson(
		await fetch(`${WEBUI_API_BASE_URL}/analysis/ops/uploads/${encodeURIComponent(uploadId)}/chunk`, {
			method: 'POST',
			headers: { authorization: `Bearer ${token}` },
			body: form
		}),
		'分块上传失败'
	);
};
