export type AnalysisPlanStep = {
	id: string;
	label: string;
	tool?: string | null;
	rules?: string[];
	depends_on?: string[];
	produces?: string;
	is_deliverable?: boolean;
};

export const buildAnalysisStageRows = (steps: AnalysisPlanStep[]): AnalysisPlanStep[][] => {
	const stepById = new Map(steps.map((step) => [step.id, step]));
	const depthById = new Map<string, number>();
	const visiting = new Set<string>();

	const depthOf = (step: AnalysisPlanStep): number => {
		const knownDepth = depthById.get(step.id);
		if (knownDepth !== undefined) return knownDepth;
		if (visiting.has(step.id)) return 0;

		visiting.add(step.id);
		const parentDepths = (step.depends_on ?? [])
			.map((id) => stepById.get(id))
			.filter((parent): parent is AnalysisPlanStep => parent !== undefined)
			.map(depthOf);
		visiting.delete(step.id);

		const depth = parentDepths.length ? Math.max(...parentDepths) + 1 : 0;
		depthById.set(step.id, depth);
		return depth;
	};

	const rows: AnalysisPlanStep[][] = [];
	for (const step of steps) {
		(rows[depthOf(step)] ??= []).push(step);
	}
	return rows;
};

export type ResourceEstimate = {
	version: 1;
	status: 'calibrated' | 'insufficient';
	duration_seconds: {
		p50: number | null;
		p90: number | null;
		budget: number | null;
	};
	peak_memory_mb: {
		p50: number | null;
		p90: number | null;
		reserve: number;
	};
	cpu_cores: number;
	confidence: 'low' | 'medium' | 'high';
	matched_runs: number;
	distinct_inputs: number;
	basis: string;
	warning: string;
};

export type AnalysisRoutingMode = 'auto' | 'emergency' | 'standard';

export type AnalysisRoutingRequest = {
	mode: AnalysisRoutingMode;
};

export type AnalysisPlanRouting = {
	requested_mode: AnalysisRoutingMode;
	effective_mode: AnalysisRoutingMode;
	adaptive: boolean;
	sample_fraction?: number;
	applicability_reason: string;
	short_circuit_scope: 'pipeline';
	available_routes: string[];
};

export const deterministicRoutingSummary = (routing: AnalysisPlanRouting) => {
	if (routing.requested_mode === 'standard') return '标准模式：直接执行完整流程';
	if (!routing.adaptive) return '目前输入不适用快速初筛，将执行标准流程';
	if (routing.requested_mode === 'emergency') return '紧急模式：5% 初筛后直接形成报告';
	return '智能模式：全部样本高置信时快速报告，否则执行完整流程';
};

export const sameAnalysisGoals = (left?: readonly string[] | null, right?: readonly string[] | null) => {
	if (!left?.length || !right?.length || left.length !== right.length) return false;
	return [...left].sort().join('\0') === [...right].sort().join('\0');
};

export const analysisPlanControlKey = (chatId: string | null | undefined, inputKey: string) =>
	JSON.stringify({ chat: chatId || null, input: inputKey });

export const canConfirmDeterministicAnalysisPlan = ({
	readyToExecute,
	goalCount,
	datasetStatus,
	routingCurrent,
	datasetCurrent,
	goalsCurrent = true,
	busy
}: {
	readyToExecute: boolean;
	goalCount: number;
	datasetStatus?: string | null;
	routingCurrent: boolean;
	datasetCurrent: boolean;
	goalsCurrent?: boolean;
	busy: boolean;
}) =>
	readyToExecute &&
	goalCount > 0 &&
	datasetStatus === 'ready' &&
	routingCurrent &&
	datasetCurrent &&
	goalsCurrent &&
	!busy;

export const isCurrentDeterministicPlanResponse = (
	requestId: number,
	currentRequestId: number,
	requestInputKey: string,
	currentInputKey: string
) => requestId === currentRequestId && requestInputKey === currentInputKey;

export type AnalysisPlanOutputItem = {
	type: 'analysis_plan';
	id: string;
	title: string;
	ready_to_execute: boolean;
	run?: {
		run_id: string;
		run_dir?: string;
		state_path?: string;
		log_path?: string;
	};
	steps: AnalysisPlanStep[];
	resource_estimate?: ResourceEstimate;
	routing?: AnalysisPlanRouting;
	blocking_reason?: string;
	dataset?: { id: string; revision: number; status: string };
};

export type AnalysisPlanMessage = {
	role?: string | null;
	hidden?: boolean | null;
	output?: unknown;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
	!!value && typeof value === 'object' && !Array.isArray(value);

const isNullableNumber = (value: unknown): value is number | null =>
	value === null || (typeof value === 'number' && Number.isFinite(value));

const isResourceEstimate = (value: unknown): value is ResourceEstimate => {
	if (!isRecord(value) || value.version !== 1) return false;
	if (value.status !== 'calibrated' && value.status !== 'insufficient') return false;
	if (!isRecord(value.duration_seconds) || !isRecord(value.peak_memory_mb)) return false;
	if (
		!isNullableNumber(value.duration_seconds.p50) ||
		!isNullableNumber(value.duration_seconds.p90) ||
		!isNullableNumber(value.duration_seconds.budget) ||
		!isNullableNumber(value.peak_memory_mb.p50) ||
		!isNullableNumber(value.peak_memory_mb.p90) ||
		typeof value.peak_memory_mb.reserve !== 'number'
	) {
		return false;
	}
	return (
		typeof value.cpu_cores === 'number' &&
		['low', 'medium', 'high'].includes(String(value.confidence)) &&
		typeof value.matched_runs === 'number' &&
		typeof value.distinct_inputs === 'number' &&
		typeof value.basis === 'string' &&
		typeof value.warning === 'string'
	);
};

const parseRouting = (value: unknown): AnalysisPlanRouting | undefined => {
	if (
		!isRecord(value) ||
		!['auto', 'emergency', 'standard'].includes(String(value.requested_mode)) ||
		!['auto', 'emergency', 'standard'].includes(String(value.effective_mode))
	) {
		return undefined;
	}
	if (
		typeof value.adaptive !== 'boolean' ||
		(value.sample_fraction !== undefined && typeof value.sample_fraction !== 'number') ||
		typeof value.applicability_reason !== 'string' ||
		value.short_circuit_scope !== 'pipeline' ||
		!Array.isArray(value.available_routes)
	) {
		return undefined;
	}
	return value as AnalysisPlanRouting;
};

const parseAnalysisPlanOutputItem = (value: unknown): AnalysisPlanOutputItem | null => {
	if (!isRecord(value) || value.type !== 'analysis_plan') return null;
	if (typeof value.id !== 'string' || typeof value.title !== 'string') return null;
	if (typeof value.ready_to_execute !== 'boolean') return null;
	if (!isRecord(value.run) || !Array.isArray(value.steps)) return null;

	const run = value.run;
	if (
		typeof run.run_id !== 'string' ||
		typeof run.run_dir !== 'string' ||
		typeof run.state_path !== 'string' ||
		typeof run.log_path !== 'string'
	) {
		return null;
	}

	if (
		!value.steps.every(
			(step) =>
				isRecord(step) &&
				typeof step.id === 'string' &&
				typeof step.label === 'string' &&
				(step.tool === undefined || step.tool === null || typeof step.tool === 'string') &&
				(step.rules === undefined ||
					(Array.isArray(step.rules) && step.rules.every((rule) => typeof rule === 'string'))) &&
				(step.depends_on === undefined ||
					(Array.isArray(step.depends_on) &&
						step.depends_on.every((id) => typeof id === 'string'))) &&
				(step.produces === undefined || typeof step.produces === 'string') &&
				(step.is_deliverable === undefined || typeof step.is_deliverable === 'boolean')
		)
	) {
		return null;
	}

	const resourceEstimate = isResourceEstimate(value.resource_estimate)
		? value.resource_estimate
		: undefined;
	const routing = parseRouting(value.routing);
	const dataset =
		isRecord(value.dataset) &&
		typeof value.dataset.id === 'string' &&
		typeof value.dataset.revision === 'number' &&
		typeof value.dataset.status === 'string'
			? {
					id: value.dataset.id,
					revision: value.dataset.revision,
					status: value.dataset.status
				}
			: undefined;
	return {
		type: 'analysis_plan',
		id: value.id,
		title: value.title,
		ready_to_execute: value.ready_to_execute,
		run: {
			run_id: run.run_id,
			run_dir: run.run_dir,
			state_path: run.state_path,
			log_path: run.log_path
		},
		steps: value.steps as AnalysisPlanStep[],
		...(resourceEstimate ? { resource_estimate: resourceEstimate } : {}),
		...(routing ? { routing } : {}),
		...(dataset ? { dataset } : {}),
		...(typeof value.blocking_reason === 'string' ? { blocking_reason: value.blocking_reason } : {})
	};
};

export const extractLatestAnalysisPlan = (
	messages: AnalysisPlanMessage[]
): AnalysisPlanOutputItem | null => {
	let latest: AnalysisPlanOutputItem | null = null;

	for (const message of messages) {
		if (message.hidden || message.role !== 'assistant' || !Array.isArray(message.output)) continue;

		for (const item of message.output) {
			const plan = parseAnalysisPlanOutputItem(item);
			if (plan) latest = plan;
		}
	}

	return latest;
};

export const isLatestAnalysisPlan = (
	plan: AnalysisPlanOutputItem,
	latest: AnalysisPlanOutputItem | null
) => plan.id === latest?.id;

export const canConfirmAnalysisPlan = (
	plan: AnalysisPlanOutputItem,
	latest: AnalysisPlanOutputItem | null,
	generating: boolean
) => isLatestAnalysisPlan(plan, latest) && plan.ready_to_execute && !generating;

export const buildAnalysisRoutingRequest = (mode: AnalysisRoutingMode): AnalysisRoutingRequest => ({
	mode
});

export const resolveAnalysisRouting = (
	planRouting: AnalysisPlanRouting | undefined,
	savedRouting: unknown
): AnalysisRoutingRequest => {
	const candidate = planRouting ?? savedRouting;
	if (!isRecord(candidate)) return { mode: 'auto' };
	const rawMode = candidate.requested_mode ?? candidate.mode;
	if (!['auto', 'emergency', 'standard'].includes(String(rawMode))) {
		return { mode: 'auto' };
	}
	return { mode: rawMode as AnalysisRoutingMode };
};

export const createAnalysisConfirmationLock = () => {
	let active = false;
	return async (action: () => Promise<void>): Promise<boolean> => {
		if (active) return false;
		active = true;
		try {
			await action();
			return true;
		} finally {
			active = false;
		}
	};
};

export const isAnalysisRoutingPlanCurrent = (
	planRouting: AnalysisPlanRouting | undefined,
	desired: AnalysisRoutingRequest
) => !planRouting || planRouting.requested_mode === desired.mode;

export const analysisPlanRequiresRouting = (_plan: AnalysisPlanOutputItem): boolean => true;

export const isAnalysisPlanRoutingCurrent = (
	plan: AnalysisPlanOutputItem | null,
	desired: AnalysisRoutingRequest
) => !plan || (!!plan.routing && isAnalysisRoutingPlanCurrent(plan.routing, desired));

export const canConfirmAnalysisPlanWithRouting = (
	plan: AnalysisPlanOutputItem,
	latest: AnalysisPlanOutputItem | null,
	generating: boolean,
	desired: AnalysisRoutingRequest
) =>
	canConfirmAnalysisPlan(plan, latest, generating) && isAnalysisPlanRoutingCurrent(plan, desired);

export const formatResourceDuration = (seconds: number | null): string => {
	if (seconds === null) return '暂不可估';
	if (seconds < 60) return `${Math.max(1, Math.round(seconds))} 秒`;
	const minutes = Math.ceil(seconds / 60);
	if (minutes < 60) return `${minutes} 分钟`;
	const hours = Math.floor(minutes / 60);
	const remainder = minutes % 60;
	return remainder ? `${hours} 小时 ${remainder} 分钟` : `${hours} 小时`;
};

export const formatResourceMemory = (megabytes: number | null): string => {
	if (megabytes === null) return '暂不可估';
	const gibibytes = megabytes / 1024;
	return `${gibibytes < 10 ? gibibytes.toFixed(1) : Math.round(gibibytes)} GiB`;
};

export const resourceConfidenceLabels: Record<ResourceEstimate['confidence'], string> = {
	low: '低',
	medium: '中',
	high: '高'
};
