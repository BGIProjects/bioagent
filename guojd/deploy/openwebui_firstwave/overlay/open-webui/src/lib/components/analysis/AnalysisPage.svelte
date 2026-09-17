<script lang="ts">
	import { getContext, onDestroy, onMount, tick } from 'svelte';

	import XvirMindBrandLockup from '$lib/components/brand/XvirMindBrandLockup.svelte';
	import BioAgentMarkdown from '$lib/components/bioagent-chat/BioAgentMarkdown.svelte';
	import Loader from '$lib/components/common/Loader.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import AppNotification from '$lib/components/icons/AppNotification.svelte';
	import ArrowUpCircle from '$lib/components/icons/ArrowUpCircle.svelte';
	import Bolt from '$lib/components/icons/Bolt.svelte';
	import ChatBubbleDotted from '$lib/components/icons/ChatBubbleDotted.svelte';
	import CheckCircle from '$lib/components/icons/CheckCircle.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import Clip from '$lib/components/icons/Clip.svelte';
	import Database from '$lib/components/icons/Database.svelte';
	import Plus from '$lib/components/icons/Plus.svelte';
	import QuestionMarkCircle from '$lib/components/icons/QuestionMarkCircle.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import Settings from '$lib/components/icons/Settings.svelte';
	import Sparkles from '$lib/components/icons/Sparkles.svelte';
	import UserCircle from '$lib/components/icons/UserCircle.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import AnalysisFileTree from '$lib/components/analysis/AnalysisFileTree.svelte';
	import AnalysisDatasetCard from '$lib/components/analysis/AnalysisDatasetCard.svelte';
	import AnalysisKnowledgePanel from '$lib/components/analysis/AnalysisKnowledgePanel.svelte';
	import AnalysisOpsPanel from '$lib/components/analysis/AnalysisOpsPanel.svelte';

	import {
		getChatById,
		getChatList,
		getChatListBySearchText,
		updateChatById
	} from '$lib/apis/chats';
	import {
		getAnalysisRunStatus,
		getAnalysisHealth,
		createAnalysisDataset,
		getAnalysisDataset,
		getAnalysisDatasetCatalog,
		reviseAnalysisDataset,
		createAnalysisPlan,
		getLatestAnalysisPlan,
		executeAnalysisPlan,
		getPendingAnalysisProposal,
		registerAnalysisProposal,
		acceptAnalysisProposal,
		rejectAnalysisProposal,
		getDiagnosticReport,
		getInternalTechnicalReport,
		type AnalysisDataset,
		type AnalysisArtifactContract,
		type AnalysisRunStatusResponse,
		type AnalysisGoal,
		type AnalysisViralType,
		type DeterministicAnalysisPlan,
		type DeterministicRoutingMode,
		type AnalysisPlanProposal,
		type AnalysisHealth,
		AnalysisApiError
	} from '$lib/apis/analysis';
	import { checkActiveChats } from '$lib/apis/tasks';
	import { activeChatIds, socket, user } from '$lib/stores';
	import { systemResources as systemResourcesStore } from '$lib/stores/systemResources';
	import {
		getEmptySystemResourceItems,
		systemResourceLabels,
		toSystemResourceItems,
		type SystemResourceTone
	} from '$lib/utils/systemResources';
	import { createBioAgentChatSession } from '$lib/utils/bioagentChat';
	import {
		buildAnalysisStageRows,
		buildAnalysisRoutingRequest,
		canConfirmDeterministicAnalysisPlan,
		createAnalysisConfirmationLock,
		sameAnalysisGoals,
		analysisPlanControlKey,
		deterministicRoutingSummary,
		formatResourceDuration,
		formatResourceMemory,
		isAnalysisPlanRoutingCurrent,
		isCurrentDeterministicPlanResponse,
		resolveAnalysisRouting,
		resourceConfidenceLabels,
		type AnalysisPlanRouting,
		type AnalysisPlanOutputItem,
		type AnalysisPlanStep
	} from '$lib/utils/analysisRun';
	import type i18nStore from '$lib/i18n';

	type RoutingMode = DeterministicRoutingMode;
	type ResourceTone = 'cyan' | 'green' | 'amber' | 'red';

	type AnalysisChatListItem = {
		id: string;
		title: string;
		updated_at: number;
		created_at: number;
		time_range?: string;
	};

	type ChatActiveSocketEvent = {
		chat_id?: string;
		data?: {
			type?: string;
			data?: {
				active?: boolean;
			};
		};
	};

	const HISTORY_PAGE_SIZE = 60;
	const ANALYSIS_CHAT_SOURCE = 'analysis';
	const ANALYSIS_RUN_STATUS_REFRESH_INTERVAL = 5000;
	const ROUTING_LABELS: Record<RoutingMode, string> = {
		auto: '智能',
		emergency: '紧急',
		standard: '标准'
	};
	const ROUTING_MODES: RoutingMode[] = ['auto', 'standard', 'emergency'];
	const ANALYSIS_GOALS: Array<{ id: AnalysisGoal; label: string; description: string }> = [
		{
			id: 'contig_filter',
			label: '质控与组装',
			description: '完成 reads 质控、去 rRNA、组装与 contig 过滤'
		},
		{ id: 'virus_summary', label: '病毒识别', description: 'W2 workflow2_virusid 候选；定种走 virus_taxonomy（确认后）' },
		{ id: 'host_summary', label: '宿主识别', description: 'W3 宿主比对、覆盖度、BLAST 与整合' },
		{ id: 'microbe_summary', label: '微生物谱', description: 'W4 Kraken2、Bracken 与分类摘要' },
		{ id: 'virus_rpm', label: '病毒定量', description: 'W5，本轮可不选' },
		{ id: 'annotation_delivery', label: '病毒注释', description: 'W6 流程注释；RNA 病毒可追加 RVA 专项' }
	];
	const VIRAL_TYPES: AnalysisViralType[] = ['RNA', 'DNA', 'RNA+DNA'];
	const FIRST_WAVE_GOALS: AnalysisGoal[] = [
		'contig_filter',
		'virus_summary',
		'host_summary',
		'microbe_summary',
		'annotation_delivery'
	];

	const collectDatasetPaths = (dataset: AnalysisDataset | null | undefined) => {
		if (!dataset) return [] as string[];
		const paths: string[] = [];
		for (const source of dataset.sources ?? []) {
			if (source?.path) paths.push(source.path);
		}
		if (paths.length) return [...new Set(paths)];
		for (const artifact of dataset.artifacts ?? []) {
			for (const record of artifact.records ?? []) {
				for (const spec of Object.values(record.files ?? {})) {
					if (spec && typeof spec === 'object' && 'path' in spec && spec.path) {
						paths.push(String(spec.path));
					}
				}
			}
		}
		return [...new Set(paths)];
	};

	const analysisChatMeta: Record<string, any> = {
		source: ANALYSIS_CHAT_SOURCE,
		analysis_routing: { mode: 'auto' }
	};
	const i18n: typeof i18nStore = getContext('i18n');
	const analysisChat = createBioAgentChatSession({
		scope: 'analysis',
		storage: 'persisted',
		keepTasksOnDetach: true,
		serverOwnedPersistence: true,
		chatMeta: analysisChatMeta,
		onPersistedChatChange: async (id) => {
			selectedHistoryId = id;
			await loadAnalysisChats({ silent: true });
		},
		greeting:
			'您好，我是 BioAgent。请在右侧文件列表打开 testdata/scenarios，勾选文件后点「确认选用并同步到对话」。会自动带上第一波目标并生成方案，再到中间确认启动。知识查询在「知识/专项」；定种与 RVA 需确认。'
	});
	const runAnalysisConfirmation = createAnalysisConfirmationLock();
	const analysisChatState = analysisChat.state;

	let confirmingAnalysis = false;
	let routingMode: RoutingMode = 'auto';
	let selectedGoals: AnalysisGoal[] = [];
	let viralType: AnalysisViralType = 'RNA+DNA';
	let deterministicPlan: DeterministicAnalysisPlan | null = null;
	let pendingProposal: AnalysisPlanProposal | null = null;
	let proposalBusy = false;
	let proposalError = '';
	let analysisHealthState: AnalysisHealth | null = null;
	const registeredProposalItems = new Set<string>();
	let plannerBusy = false;
	let plannerError = '';
	let plannerErrorCode: string | null = null;
	let planRequestId = 0;
	let lastPlanControlKey = '';
	let selectedHistoryId: string | null = null;
	let rightMode: 'status' | 'files' | 'knowledge' | 'ops' = 'status';
	let draft = '';
	let analysisRunStatus: AnalysisRunStatusResponse | null = null;
	let analysisRunStatusLoading = false;
	let analysisRunStatusError = '';
	let analysisRunStatusInterval: ReturnType<typeof setInterval> | null = null;
	let loadedAnalysisRunKey: string | null = null;
	let analysisChats: AnalysisChatListItem[] = [];
	let analysisChatPage = 1;
	let allHistoryItemsLoaded = false;
	let analysisChatsLoading = true;
	let analysisChatsError = '';
	let historySearchOpen = false;
	let historySearchQuery = '';
	let historyListLoading = false;
	let historySearchDebounce: ReturnType<typeof setTimeout> | null = null;
	let historyRequestId = 0;
	let historySearchInput: HTMLInputElement;
	let renameInput: HTMLInputElement;
	let editingChatId: string | null = null;
	let editingTitle = '';
	let renamingChatId: string | null = null;
	let downloadingCurrentReport = false;
	let currentReportDownloadError = '';
	let downloadingInternalReport = false;
	let internalReportDownloadError = '';
	let selectedAnalysisFilePaths: string[] = [];
	let activeDataset: AnalysisDataset | null = null;
	let datasetCatalog: AnalysisArtifactContract[] = [];
	let datasetBusy = false;
	let datasetError = '';
	let datasetInterval: ReturnType<typeof setInterval> | null = null;
	let messageViewport: HTMLDivElement;
	let draftInput: HTMLTextAreaElement;
	let activeChatSocket: any = null;
	let unsubscribeActiveChatSocket: (() => void) | null = null;

	$: visibleHistoryItems = analysisChats;
	$: visibleLiveMessages = $analysisChatState.messages.filter((message) => !message.hidden);
	$: activeAnalysisPlan = (
		selectedGoals.length > 0 ? deterministicPlan : null
	) as AnalysisPlanOutputItem | null;
	$: activeAnalysisRun = activeAnalysisPlan?.run ?? null;
	$: desiredRouting = getDesiredRouting();
	$: plannerInputKey = JSON.stringify({
		dataset: activeDataset
			? [activeDataset.dataset_id, activeDataset.revision, activeDataset.status]
			: null,
		goals: selectedGoals,
		viralType,
		routing: desiredRouting
	});
	$: planControlKey = JSON.stringify({
		chat: $analysisChatState.chatId || null,
		input: plannerInputKey
	});
	$: if (
		planControlKey !== lastPlanControlKey &&
		selectedGoals.length > 0 &&
		activeDataset &&
		['checking', 'ready'].includes(activeDataset.status) &&
		!plannerBusy
	) {
		void regeneratePlan(planControlKey);
	}
	$: routingPlanCurrent = isAnalysisPlanRoutingCurrent(activeAnalysisPlan, desiredRouting);
	$: datasetPlanCurrent = Boolean(
		activeDataset &&
		activeAnalysisPlan?.dataset?.id === activeDataset.dataset_id &&
		activeAnalysisPlan?.dataset?.revision === activeDataset.revision
	);
	$: goalsPlanCurrent = sameAnalysisGoals(selectedGoals, deterministicPlan?.goals);
	$: canConfirmCurrentPlan = canConfirmDeterministicAnalysisPlan({
		readyToExecute: Boolean(deterministicPlan?.ready_to_execute),
		goalCount: selectedGoals.length,
		datasetStatus: activeDataset?.status,
		routingCurrent: routingPlanCurrent,
		datasetCurrent: datasetPlanCurrent,
		goalsCurrent: goalsPlanCurrent,
		busy: plannerBusy || confirmingAnalysis || Boolean(pendingProposal)
	});
	$: confirmBlockReason = pendingProposal
		? '请先接受或拒绝待确认的方案修改'
		: plannerBusy
			? '正在按当前勾选重编方案…'
			: !selectedGoals.length
				? '请至少选择一项分析目标'
				: activeDataset?.status !== 'ready'
					? deterministicPlan?.blocking_reason || '数据集尚未完成预检，完成后会自动重编方案'
					: !goalsPlanCurrent
						? '方案尚未跟上当前勾选（定量/注释等），请稍候重编完成'
						: !datasetPlanCurrent
							? '方案绑定的数据集已变化，请等待重编'
							: !routingPlanCurrent
								? '路由模式已变化，请等待重编'
								: deterministicPlan && !deterministicPlan.ready_to_execute
									? deterministicPlan.blocking_reason || '方案尚未可执行'
									: '';
	$: analysisChatMeta.analysis_routing = desiredRouting;
	$: analysisChatMeta.analysis_goals = selectedGoals;
	$: analysisChatMeta.analysis_options = { viral_type: viralType };
	$: analysisChatMeta.analysis_dataset = activeDataset
		? {
				id: activeDataset.dataset_id,
				revision: activeDataset.revision,
				status: activeDataset.status,
				files: collectDatasetPaths(activeDataset),
				records: (activeDataset.artifacts ?? []).reduce(
					(count, artifact) => count + (artifact.records?.length ?? 0),
					0
				)
			}
		: undefined;
	$: analysisChatMeta.analysis_plan_summary = deterministicPlan
		? {
				id: deterministicPlan.id,
				revision: deterministicPlan.revision,
				goals: deterministicPlan.goals,
				ready_to_execute: deterministicPlan.ready_to_execute,
				summary: deterministicPlan.summary,
				title: deterministicPlan.title,
				blocking_reason: deterministicPlan.blocking_reason ?? null
			}
		: undefined;
	$: activeAnalysisRunKey = activeAnalysisRun?.run_dir ?? activeAnalysisRun?.run_id ?? null;
	$: activeAnalysisRunId = analysisRunStatus?.run_id ?? activeAnalysisRun?.run_id ?? null;
	$: activeAnalysisRunDir = analysisRunStatus?.run_dir ?? activeAnalysisRun?.run_dir ?? null;

	$: selectedAnalysisChat = analysisChats.find((item) => item.id === selectedHistoryId) ?? null;
	$: hasLiveMessageError = $analysisChatState.messages.some((message) => Boolean(message.error));
	$: latestPatchOutput = [...$analysisChatState.messages]
		.reverse()
		.flatMap((message) => (message.output ?? []).map((item: any) => ({ message, item })))
		.find(
			({ item }) =>
				item?.type === 'analysis_patch_proposal' && item?.status === 'pending_registration'
		);
	$: if (
		latestPatchOutput &&
		deterministicPlan &&
		$analysisChatState.chatId &&
		pendingProposal?.message_id !== latestPatchOutput.message.id
	) {
		void registerModelProposal(latestPatchOutput.message, latestPatchOutput.item);
	}
	$: resourceStatusLabel = $systemResourcesStore.unavailable
		? '无法读取'
		: $systemResourcesStore.data
			? '实时更新'
			: '读取中';
	$: systemResourceItems = $systemResourcesStore.data
		? toSystemResourceItems($systemResourcesStore.data, systemResourceLabels.zh)
		: getEmptySystemResourceItems(
				systemResourceLabels.zh,
				$systemResourcesStore.unavailable ? '无法读取' : '读取中'
			);
	$: plannedAnalysisRunTasks = getPlannedAnalysisRunTasks(activeAnalysisPlan);
	$: analysisRunTasks = analysisRunStatus?.run_id
		? analysisRunStatus.tasks
		: plannedAnalysisRunTasks;
	$: analysisRunStatusLabel = getAnalysisRunStatusLabel(
		analysisRunStatus,
		analysisRunStatusLoading,
		activeAnalysisPlan
	);
	$: analysisRunStepText = getAnalysisRunStepText(analysisRunStatus, activeAnalysisPlan);
	$: if (activeAnalysisRunKey !== loadedAnalysisRunKey) {
		loadedAnalysisRunKey = activeAnalysisRunKey;
		resetAnalysisRunStatus();
		if (activeAnalysisRun) {
			void loadAnalysisRunStatus({
				runId: activeAnalysisRun.run_id,
				runDir: activeAnalysisRun.run_dir,
				runKey: activeAnalysisRunKey
			});
		}
	}

	const getAnalysisRunStatusLabel = (
		status: AnalysisRunStatusResponse | null,
		loading: boolean,
		plan: AnalysisPlanOutputItem | null
	) => {
		if (loading && !status) return '读取中';
		if (analysisRunStatusError) return '无法读取';
		if (!status?.run_id && plan) return plan.ready_to_execute ? '等待启动' : '方案待确认';
		if (!status?.run_id) return '暂无任务';
		if (status.status === 'done') return '已完成';
		if (status.status === 'blocked') return '资源不足';
		if (status.status === 'failed') return '运行失败';
		if (status.status === 'planned') return '等待启动';
		if (status.status === 'running') return '运行中';
		return '实时更新';
	};

	const getAnalysisRunStepText = (
		status: AnalysisRunStatusResponse | null,
		plan: AnalysisPlanOutputItem | null
	) => {
		if (status?.run_id && status.total_steps > 0) {
			return `${status.completed_steps}/${status.total_steps}`;
		}
		if (plan?.steps.length) {
			return `0/${plan.steps.length}`;
		}
		return '';
	};

	const getResourceEstimate = (plan: AnalysisPlanOutputItem | null) =>
		plan?.resource_estimate ?? null;

	const getDesiredRouting = () => buildAnalysisRoutingRequest(routingMode);

	const routingPhaseLabel = (phase?: string) =>
		({
			screening_admission: '资源检查',
			screening: '5% 初筛中',
			selected: '路径已选择',
			full_analysis: '完整分析中',
			completed: '路由完成',
			blocked: '资源阻断',
			failed: '路由失败'
		})[phase ?? ''] ?? '等待初筛';

	const getDisplayedPipelineSteps = (plan: AnalysisPlanOutputItem) =>
		plan.routing
			? plan.steps.filter((step) => step.id !== 'adaptive_screen' && step.id !== 'adaptive_route')
			: plan.steps;

	const getPlannedAnalysisRunTasks = (plan: AnalysisPlanOutputItem | null) => {
		if (!plan || !plan.run) return [];

		return [
			{
				id: plan.run.run_id,
				sample: plan.title || plan.run.run_id,
				stage: plan.ready_to_execute ? '等待启动' : '方案待确认',
				progress: 0,
				tone: 'cyan' as const
			}
		];
	};

	const getMessageTime = (timestamp: number) =>
		new Date(timestamp * 1000).toLocaleTimeString('zh-CN', {
			hour: '2-digit',
			minute: '2-digit'
		});

	const toneClass = (tone: ResourceTone | SystemResourceTone) => `tone-${tone}`;

	$: if (messageViewport && $analysisChatState.messages.length) {
		tick().then(() => {
			messageViewport?.scrollTo({ top: messageViewport.scrollHeight, behavior: 'smooth' });
		});
	}

	const scrollMessagesToBottom = async () => {
		await tick();
		messageViewport?.scrollTo({ top: messageViewport.scrollHeight, behavior: 'smooth' });
	};

	const ensureLiveConversation = async () => {
		if (!$analysisChatState.model) {
			await analysisChat.loadModel(analysisHealthState?.conversation_model.id ?? 'BioAgent');
		}
	};

	const sendToBioAgent = async (text: string) => {
		if (!text.trim() || $analysisChatState.generating) return;

		await ensureLiveConversation();
		await analysisChat.send(text);
		await scrollMessagesToBottom();
	};

	const registerModelProposal = async (message: any, item: any) => {
		const chatId = $analysisChatState.chatId;
		if (!chatId || !deterministicPlan || !item?.patch) return;
		const key = `${chatId}:${message.id}:${JSON.stringify(item.patch)}`;
		if (registeredProposalItems.has(key)) return;
		registeredProposalItems.add(key);
		proposalError = '';
		try {
			const proposal = await registerAnalysisProposal(localStorage.token, chatId, {
				base_plan_revision: deterministicPlan.revision,
				proposal_id: item.id,
				patch: item.patch,
				citations: Array.isArray(item.citations) ? item.citations : [],
				model: message.model,
				message_id: message.id
			});
			pendingProposal = proposal.status === 'pending' ? proposal : null;
		} catch (error) {
			registeredProposalItems.delete(key);
			proposalError = error instanceof Error ? error.message : '无法登记方案修改提案';
		}
	};

	const acceptProposal = async () => {
		if (!pendingProposal || proposalBusy) return;
		proposalBusy = true;
		proposalError = '';
		try {
			const response = await acceptAnalysisProposal(localStorage.token, pendingProposal.id);
			deterministicPlan = response.plan;
			selectedGoals = response.plan.goals;
			viralType = response.plan.options.viral_type;
			pendingProposal = null;
			lastPlanControlKey = planControlKey;
		} catch (error) {
			proposalError = error instanceof Error ? error.message : '无法接受方案修改提案';
		} finally {
			proposalBusy = false;
		}
	};

	const rejectProposal = async () => {
		if (!pendingProposal || proposalBusy) return;
		proposalBusy = true;
		proposalError = '';
		try {
			await rejectAnalysisProposal(localStorage.token, pendingProposal.id);
			pendingProposal = null;
		} catch (error) {
			proposalError = error instanceof Error ? error.message : '无法拒绝方案修改提案';
		} finally {
			proposalBusy = false;
		}
	};

	const submitDraft = async () => {
		const text = draft.trim();
		if (!text) return;
		if ($analysisChatState.generating) return;

		draft = '';
		await sendToBioAgent(text);
	};

	const toggleGoal = (goal: AnalysisGoal) => {
		selectedGoals = selectedGoals.includes(goal)
			? selectedGoals.filter((value) => value !== goal)
			: [...selectedGoals, goal];
		lastPlanControlKey = '';
	};

	const regeneratePlan = async (controlKey: string, retry = true) => {
		if (
			plannerBusy ||
			selectedGoals.length === 0 ||
			!activeDataset ||
			!['checking', 'ready'].includes(activeDataset.status)
		)
			return;

		const requestId = ++planRequestId;
		const requestInputKey = plannerInputKey;
		plannerBusy = true;
		plannerError = '';
		plannerErrorCode = null;
		lastPlanControlKey = controlKey;
		try {
			const response = await createAnalysisPlan(localStorage.token, {
				...($analysisChatState.chatId ? { chat_id: $analysisChatState.chatId } : {}),
				dataset: { id: activeDataset.dataset_id, revision: activeDataset.revision },
				goals: selectedGoals,
				options: { viral_type: viralType },
				routing: desiredRouting as { mode: RoutingMode },
				...(deterministicPlan ? { base_plan_revision: deterministicPlan.revision } : {})
			});
			if (
				!isCurrentDeterministicPlanResponse(
					requestId,
					planRequestId,
					requestInputKey,
					plannerInputKey
				)
			)
				return;
			if (!$analysisChatState.chatId) {
				const chat = await getChatById(localStorage.token, response.chat_id);
				await analysisChat.loadChat(chat);
				selectedHistoryId = response.chat_id;
				await loadAnalysisChats({ silent: true });
			}
			deterministicPlan = response.plan;
			if (analysisHealthState) {
				analysisHealthState = {
					...analysisHealthState,
					deterministic: { status: 'ready' }
				};
			}
			lastPlanControlKey = analysisPlanControlKey($analysisChatState.chatId, requestInputKey);
		} catch (error) {
			if (
				!isCurrentDeterministicPlanResponse(
					requestId,
					planRequestId,
					requestInputKey,
					plannerInputKey
				)
			)
				return;
			const message = error instanceof Error ? error.message : '无法生成分析方案';
			if (retry && $analysisChatState.chatId && message.includes('revision conflict')) {
				try {
					deterministicPlan = (
						await getLatestAnalysisPlan(localStorage.token, $analysisChatState.chatId)
					).plan;
					plannerBusy = false;
					await regeneratePlan(controlKey, false);
					return;
				} catch {
					// Fall through to the original conflict message.
				}
			}
			plannerError = message;
			plannerErrorCode = error instanceof AnalysisApiError ? (error.code ?? null) : null;
			if (plannerErrorCode === 'PLANNER_UNAVAILABLE' && analysisHealthState) {
				analysisHealthState = {
					...analysisHealthState,
					deterministic: { status: 'unavailable' }
				};
			}
		} finally {
			if (requestId === planRequestId) plannerBusy = false;
		}
	};

	const confirmAnalysis = async () => {
		const plan = deterministicPlan;
		if (!plan || !canConfirmCurrentPlan) return;

		await runAnalysisConfirmation(async () => {
			confirmingAnalysis = true;
			rightMode = 'status';
			try {
				deterministicPlan = (await executeAnalysisPlan(localStorage.token, plan.id, plan.revision))
					.plan;
				plannerErrorCode = null;
				if (analysisHealthState) {
					analysisHealthState = {
						...analysisHealthState,
						deterministic: { status: 'ready' }
					};
				}
			} catch (error) {
				plannerError = error instanceof Error ? error.message : '无法启动分析';
				plannerErrorCode = error instanceof AnalysisApiError ? (error.code ?? null) : null;
				if (plannerErrorCode === 'PLANNER_UNAVAILABLE' && analysisHealthState) {
					analysisHealthState = {
						...analysisHealthState,
						deterministic: { status: 'unavailable' }
					};
				}
			} finally {
				confirmingAnalysis = false;
			}
		});
	};

	const adjustRequirements = async () => {
		await ensureLiveConversation();
		draft = draft.trim() ? draft : '我想调整需求：';
		await tick();
		draftInput?.focus();
	};

	const downloadCurrentDiagnosticReport = async () => {
		if (
			downloadingCurrentReport ||
			!activeAnalysisRunId ||
			!activeAnalysisRunDir ||
			!analysisRunStatus?.report_available
		) {
			return;
		}

		downloadingCurrentReport = true;
		currentReportDownloadError = '';
		try {
			const blob = await getDiagnosticReport(localStorage.token, activeAnalysisRunDir);
			const url = URL.createObjectURL(blob);
			const anchor = document.createElement('a');
			anchor.href = url;
			anchor.download = `${activeAnalysisRunId}-diagnostic-opinion.html`;
			document.body.appendChild(anchor);
			anchor.click();
			anchor.remove();
			setTimeout(() => URL.revokeObjectURL(url), 0);
		} catch (error) {
			console.error(error);
			currentReportDownloadError = '诊断意见书下载失败';
		} finally {
			downloadingCurrentReport = false;
		}
	};

	const downloadInternalReport = async () => {
		const chatId = $analysisChatState.chatId || selectedHistoryId;
		if (
			downloadingInternalReport ||
			!chatId ||
			!activeAnalysisRunId ||
			!activeAnalysisRunDir ||
			!analysisRunStatus?.internal_report_available
		) {
			return;
		}

		downloadingInternalReport = true;
		internalReportDownloadError = '';
		try {
			const blob = await getInternalTechnicalReport(
				localStorage.token,
				chatId,
				activeAnalysisRunDir
			);
			const url = URL.createObjectURL(blob);
			const anchor = document.createElement('a');
			anchor.href = url;
			anchor.download = `${activeAnalysisRunId}-internal-technical-report.html`;
			document.body.appendChild(anchor);
			anchor.click();
			anchor.remove();
			setTimeout(() => URL.revokeObjectURL(url), 0);
		} catch (error) {
			console.error(error);
			internalReportDownloadError = '内部技术报告下载失败';
		} finally {
			downloadingInternalReport = false;
		}
	};

	const syncDatasetToConversation = async () => {
		if (!activeDataset) return;
		const files = collectDatasetPaths(activeDataset);
		const fileLines = files.length
			? files.map((item, index) => `${index + 1}. ${item}`).join('\n')
			: '（数据集未带上文件路径，请重新勾选后点确认选用）';
		const goalText = selectedGoals.length ? selectedGoals.join(', ') : '尚未选择';
		const planText = deterministicPlan
			? `${deterministicPlan.title || '已生成方案'}；${deterministicPlan.ready_to_execute ? '可以确认启动' : deterministicPlan.blocking_reason || '尚未可执行'}`
			: plannerError || '方案尚未生成';
		await sendToBioAgent(
			[
				'已确认选用当前数据集，请同步到对话并列出计算方案。',
				`数据集 ${activeDataset.dataset_id} revision ${activeDataset.revision} 状态 ${activeDataset.status}。`,
				`文件 ${files.length} 个：`,
				fileLines,
				`目标：${goalText}。`,
				`方案：${planText}。确认启动请点中间「确认启动分析」。`
			].join('\n')
		);
	};

	const confirmInferredGrouping = async () => {
		if (!activeDataset || activeDataset.status !== 'needs_review') return;
		if (!(activeDataset.artifacts ?? []).length) return;
		activeDataset = await reviseAnalysisDataset(
			localStorage.token,
			activeDataset.dataset_id,
			activeDataset.revision,
			activeDataset.artifacts
		);
	};

	const createDatasetFromSelection = async (paths: string[]) => {
		if (paths.length === 0 || datasetBusy) return;
		datasetBusy = true;
		datasetError = '';
		plannerError = '';
		try {
			activeDataset = await createAnalysisDataset(localStorage.token, paths);
			selectedAnalysisFilePaths = [];
			await confirmInferredGrouping();
			if (selectedGoals.length === 0) {
				selectedGoals = [...FIRST_WAVE_GOALS];
			}
			await tick();
			lastPlanControlKey = '';
			await regeneratePlan(planControlKey);
			await syncDatasetToConversation();
		} catch (error) {
			datasetError = error instanceof Error ? error.message : '无法创建数据集';
		} finally {
			datasetBusy = false;
		}
		rightMode = 'files';
	};

	const saveDatasetRevision = async (artifacts: Array<Record<string, any>>) => {
		if (!activeDataset || datasetBusy) return;
		datasetBusy = true;
		datasetError = '';
		try {
			activeDataset = await reviseAnalysisDataset(
				localStorage.token,
				activeDataset.dataset_id,
				activeDataset.revision,
				artifacts
			);
		} catch (error) {
			datasetError = error instanceof Error ? error.message : '无法修订数据集';
		} finally {
			datasetBusy = false;
		}
	};

	const replanDataset = async () => {
		if (!activeDataset) {
			datasetError = '请先在文件列表勾选文件，再点「确认选用并同步到对话」';
			return;
		}
		if (selectedGoals.length === 0) {
			selectedGoals = [...FIRST_WAVE_GOALS];
		}
		if (activeDataset.status === 'needs_review') {
			try {
				await confirmInferredGrouping();
			} catch (error) {
				plannerError = error instanceof Error ? error.message : '请先在数据集卡片确认 sample 分组';
				return;
			}
		}
		if (!['checking', 'ready'].includes(activeDataset.status)) {
			plannerError = `数据集状态为 ${activeDataset.status}，还不能生成方案`;
			return;
		}
		lastPlanControlKey = '';
		await tick();
		await regeneratePlan(planControlKey);
		if (!deterministicPlan && !plannerError) {
			plannerError = '未能生成方案，请确认已选择分析目标';
		}
		await syncDatasetToConversation();
	};

	const refreshDataset = async () => {
		if (!activeDataset || activeDataset.status !== 'checking') return;
		try {
			activeDataset = await getAnalysisDataset(
				localStorage.token,
				activeDataset.dataset_id,
				activeDataset.revision
			);
		} catch (error) {
			datasetError = error instanceof Error ? error.message : '无法刷新数据集';
		}
	};

	const getAnalysisChatPage = async (page: number, query: string) => {
		if (query) {
			return await getChatListBySearchText(localStorage.token, query, page, {
				source: ANALYSIS_CHAT_SOURCE
			});
		}

		return await getChatList(localStorage.token, page, false, false, {
			source: ANALYSIS_CHAT_SOURCE
		});
	};

	const mergeAnalysisChats = (
		currentChats: AnalysisChatListItem[],
		nextChats: AnalysisChatListItem[]
	) => {
		const existingIds = new Set(currentChats.map((chat) => chat.id));
		return [...currentChats, ...nextChats.filter((chat) => !existingIds.has(chat.id))];
	};

	const updateActiveAnalysisChats = (checkedIds: string[], activeIds: string[]) => {
		const checked = new Set(checkedIds);
		activeChatIds.update((ids) => {
			const next = new Set(ids);
			for (const id of checked) next.delete(id);
			for (const id of activeIds) next.add(id);
			return next;
		});
	};

	const refreshActiveAnalysisChats = async (items = analysisChats) => {
		const chatIds = items.map((chat) => chat.id).filter(Boolean);
		if (chatIds.length === 0) return;

		try {
			const response = await checkActiveChats(localStorage.token, chatIds);
			updateActiveAnalysisChats(chatIds, response?.active_chat_ids ?? []);
		} catch (error) {
			console.debug('Failed to check active analysis chats:', error);
		}
	};

	const handleChatActiveEvent = (event: ChatActiveSocketEvent) => {
		if (!event.chat_id || event.data?.type !== 'chat:active') return;

		activeChatIds.update((ids) => {
			const next = new Set(ids);
			if (event.data?.data?.active) {
				next.add(event.chat_id as string);
			} else {
				next.delete(event.chat_id as string);
			}
			return next;
		});
	};

	const loadAnalysisChats = async ({
		silent = false,
		page = 1,
		append = false,
		query = historySearchQuery.trim()
	} = {}) => {
		const requestId = ++historyRequestId;

		if (append) {
			historyListLoading = true;
		} else if (!silent) {
			analysisChatsLoading = true;
		}

		if (!append) {
			analysisChatsError = '';
			allHistoryItemsLoaded = false;
			historyListLoading = false;
		}

		try {
			const chats = await getAnalysisChatPage(page, query);
			if (requestId !== historyRequestId) return;

			analysisChatPage = page;
			allHistoryItemsLoaded = chats.length < HISTORY_PAGE_SIZE;
			analysisChats = append ? mergeAnalysisChats(analysisChats, chats) : chats;
			void refreshActiveAnalysisChats(analysisChats);
		} catch (error) {
			console.error(error);
			if (!append) {
				analysisChatsError = '无法读取历史对话';
			}
		} finally {
			if (requestId !== historyRequestId) return;

			if (append) {
				historyListLoading = false;
			} else {
				analysisChatsLoading = false;
			}
		}
	};

	const selectHistory = async (id: string) => {
		cancelRename();

		const chat = await getChatById(localStorage.token, id).catch((error) => {
			console.error(error);
			analysisChatsError = '无法打开该对话';
			return null;
		});
		if (!chat) return;

		selectedHistoryId = id;
		const savedRouting = chat?.meta?.analysis_routing ?? chat?.chat?.meta?.analysis_routing;
		const savedDataset = chat?.meta?.analysis_dataset ?? chat?.chat?.meta?.analysis_dataset;
		const savedGoals = chat?.meta?.analysis_goals ?? chat?.chat?.meta?.analysis_goals;
		const savedOptions = chat?.meta?.analysis_options ?? chat?.chat?.meta?.analysis_options;
		draft = '';
		activeDataset = null;
		deterministicPlan = null;
		pendingProposal = null;
		proposalError = '';
		selectedGoals = Array.isArray(savedGoals) ? savedGoals : [];
		viralType = ['RNA', 'DNA', 'RNA+DNA'].includes(savedOptions?.viral_type)
			? savedOptions.viral_type
			: 'RNA+DNA';
		datasetError = '';
		plannerError = '';
		lastPlanControlKey = '';
		resetAnalysisRunStatus();
		await analysisChat.loadChat(chat);
		try {
			deterministicPlan = (await getLatestAnalysisPlan(localStorage.token, id)).plan;
			selectedGoals = deterministicPlan.goals;
			viralType = deterministicPlan.options.viral_type;
			pendingProposal = await getPendingAnalysisProposal(localStorage.token, id);
		} catch {}
		const restoredRouting = resolveAnalysisRouting(
			deterministicPlan?.routing as AnalysisPlanRouting | undefined,
			savedRouting
		);
		if (restoredRouting && ['auto', 'emergency', 'standard'].includes(restoredRouting.mode)) {
			routingMode = restoredRouting.mode as RoutingMode;
		}
		const datasetReference = deterministicPlan?.dataset ?? savedDataset;
		if (
			datasetReference &&
			typeof datasetReference.id === 'string' &&
			typeof datasetReference.revision === 'number'
		) {
			try {
				activeDataset = await getAnalysisDataset(
					localStorage.token,
					datasetReference.id,
					datasetReference.revision
				);
			} catch (error) {
				datasetError = error instanceof Error ? error.message : '无法恢复数据集';
			}
		}
		loadedAnalysisRunKey = null;
		await scrollMessagesToBottom();
	};

	const startNewConversation = async () => {
		cancelRename();

		selectedHistoryId = null;
		routingMode = 'auto';
		selectedGoals = [];
		viralType = 'RNA+DNA';
		deterministicPlan = null;
		pendingProposal = null;
		proposalError = '';
		plannerError = '';
		lastPlanControlKey = '';
		draft = '';
		activeDataset = null;
		datasetError = '';
		resetAnalysisRunStatus();
		loadedAnalysisRunKey = null;
		analysisChat.reset();
		await analysisChat.loadModel(analysisHealthState?.conversation_model.id ?? 'BioAgent');
		await scrollMessagesToBottom();
	};

	const startRename = async (chat: AnalysisChatListItem) => {
		editingChatId = chat.id;
		editingTitle = chat.title;
		await tick();
		renameInput?.focus();
		renameInput?.select();
	};

	const cancelRename = () => {
		editingChatId = null;
		editingTitle = '';
	};

	const saveRename = async (id: string) => {
		const title = editingTitle.trim();
		if (!title || renamingChatId) {
			cancelRename();
			return;
		}

		renamingChatId = id;
		try {
			await updateChatById(localStorage.token, id, { title });
			analysisChats = analysisChats.map((chat) => (chat.id === id ? { ...chat, title } : chat));
			cancelRename();
			await loadAnalysisChats();
		} finally {
			renamingChatId = null;
		}
	};

	const toggleHistorySearch = async () => {
		historySearchOpen = !historySearchOpen;

		if (!historySearchOpen) {
			historySearchQuery = '';
			clearHistorySearchDebounce();
			await loadAnalysisChats({ query: '' });
			return;
		}

		await tick();
		historySearchInput?.focus();
	};

	const clearHistorySearch = async () => {
		historySearchQuery = '';
		clearHistorySearchDebounce();
		await loadAnalysisChats({ query: '' });
		await tick();
		historySearchInput?.focus();
	};

	const clearHistorySearchDebounce = () => {
		if (!historySearchDebounce) return;

		clearTimeout(historySearchDebounce);
		historySearchDebounce = null;
	};

	const queueHistorySearch = (query: string) => {
		historySearchQuery = query;
		clearHistorySearchDebounce();
		historySearchDebounce = setTimeout(() => {
			historySearchDebounce = null;
			void loadAnalysisChats({ query: historySearchQuery.trim() });
		}, 400);
	};

	const handleHistorySearchInput = (event: Event) => {
		queueHistorySearch((event.currentTarget as HTMLInputElement).value);
	};

	const loadMoreHistory = async () => {
		if (analysisChatsLoading || historyListLoading || allHistoryItemsLoaded) return;

		await loadAnalysisChats({
			page: analysisChatPage + 1,
			append: true,
			query: historySearchQuery.trim()
		});
	};

	function resetAnalysisRunStatus() {
		analysisRunStatus = null;
		analysisRunStatusLoading = false;
		analysisRunStatusError = '';
	}

	async function loadAnalysisRunStatus({
		silent = false,
		runId = activeAnalysisRun?.run_id ?? null,
		runDir = activeAnalysisRun?.run_dir ?? null,
		runKey = activeAnalysisRunKey
	}: {
		silent?: boolean;
		runId?: string | null;
		runDir?: string | null;
		runKey?: string | null;
	} = {}) {
		if (!runId && !runDir) {
			resetAnalysisRunStatus();
			return;
		}

		if (!silent) {
			analysisRunStatusLoading = true;
		}
		analysisRunStatusError = '';

		try {
			const status = await getAnalysisRunStatus(localStorage.token, { runId, runDir });
			if (runKey !== activeAnalysisRunKey) return;

			analysisRunStatus = status;
		} catch (error) {
			if (runKey !== activeAnalysisRunKey) return;
			console.error(error);
			analysisRunStatusError = '无法读取分析任务状态';
		} finally {
			if (runKey === activeAnalysisRunKey) {
				analysisRunStatusLoading = false;
			}
		}
	}

	onMount(() => {
		void loadAnalysisChats();
		void getAnalysisHealth(localStorage.token).then((value) => (analysisHealthState = value));
		void getAnalysisDatasetCatalog(localStorage.token)
			.then((value) => (datasetCatalog = value.artifacts))
			.catch(
				(error) => (datasetError = error instanceof Error ? error.message : '无法读取数据集类型')
			);
		unsubscribeActiveChatSocket = socket.subscribe(($socket) => {
			if (activeChatSocket === $socket) return;

			activeChatSocket?.off('events', handleChatActiveEvent);
			activeChatSocket = $socket;
			activeChatSocket?.on('events', handleChatActiveEvent);
		});
		analysisRunStatusInterval = setInterval(
			() => void loadAnalysisRunStatus({ silent: true }),
			ANALYSIS_RUN_STATUS_REFRESH_INTERVAL
		);
		datasetInterval = setInterval(() => void refreshDataset(), 2000);
	});

	onDestroy(() => {
		clearHistorySearchDebounce();
		unsubscribeActiveChatSocket?.();
		activeChatSocket?.off('events', handleChatActiveEvent);
		if (analysisRunStatusInterval) {
			clearInterval(analysisRunStatusInterval);
		}
		if (datasetInterval) clearInterval(datasetInterval);
		analysisChat.destroy();
	});
</script>

<div class="analysis-page">
	<header class="analysis-header">
		<XvirMindBrandLockup href="/dashboard" ariaLabel="打开仪表盘" />

		<div class="header-title">
			<ChatBubbleDotted className="size-6" strokeWidth="1.8" />
			<div>
				<h1>AI 分析对话</h1>
				<p>BioAgent 真实分析对话</p>
			</div>
		</div>

		<div class="header-actions">
			<a class="header-link" href="/dashboard">监控看板</a>
			<button type="button" class="icon-button" aria-label="通知">
				<AppNotification className="size-5" strokeWidth="1.8" />
			</button>
			<button type="button" class="icon-button" aria-label="帮助">
				<QuestionMarkCircle className="size-5" strokeWidth="1.8" />
			</button>
			<button type="button" class="user-button">
				<UserCircle className="size-7" strokeWidth="1.7" />
				<span>XvirMind 用户</span>
				<ChevronDown className="size-4" strokeWidth="1.8" />
			</button>
		</div>
	</header>

	<div class="analysis-grid">
		<aside class="history-panel panel">
			<button
				type="button"
				class:active={!selectedHistoryId}
				class="new-chat-button"
				on:click={startNewConversation}
			>
				<Plus className="size-5" strokeWidth="1.8" />
				<span>新建对话</span>
			</button>

			<div class="panel-title-row">
				<h2>历史对话</h2>
				<button
					type="button"
					class:active={historySearchOpen}
					class="panel-icon-button"
					aria-label="搜索历史对话"
					aria-pressed={historySearchOpen}
					on:click={toggleHistorySearch}
				>
					<Search className="size-5" strokeWidth="1.8" />
				</button>
			</div>

			{#if historySearchOpen}
				<div class="history-search">
					<Search className="size-4" strokeWidth="1.8" />
					<input
						bind:this={historySearchInput}
						bind:value={historySearchQuery}
						type="search"
						aria-label="搜索历史对话"
						placeholder="搜索标题或对话 ID"
						on:input={handleHistorySearchInput}
					/>
					{#if historySearchQuery}
						<button type="button" aria-label="清除搜索" on:click={clearHistorySearch}>
							<XMark className="size-4" />
						</button>
					{/if}
				</div>
			{/if}

			<div
				class="history-list"
				aria-label={historySearchQuery ? '历史对话搜索结果' : '历史对话列表'}
			>
				{#if analysisChatsLoading}
					<div class="history-loader">
						<Spinner className="size-4" />
						<span>加载历史对话</span>
					</div>
				{:else if analysisChatsError}
					<div class="history-empty">
						<XMark className="size-6" strokeWidth="1.7" />
						<strong>{analysisChatsError}</strong>
						<span>稍后重试</span>
					</div>
				{:else if visibleHistoryItems.length > 0}
					{#each visibleHistoryItems as item (item.id)}
						{@const isActiveChat = $activeChatIds.has(item.id)}
						<div class:selected={item.id === selectedHistoryId} class="history-item">
							{#if editingChatId === item.id}
								<div class="history-main editing">
									<span class:active={isActiveChat} class="history-leading">
										{#if isActiveChat}
											<Spinner className="size-4" />
										{:else}
											<ChatBubbleDotted className="size-5" strokeWidth="1.6" />
										{/if}
									</span>
									<span class="history-copy">
										<input
											bind:this={renameInput}
											bind:value={editingTitle}
											class="history-title-input"
											aria-label="编辑对话标题"
											on:click|stopPropagation
											on:keydown={(event) => {
												if (event.key === 'Enter') {
													event.preventDefault();
													saveRename(item.id);
												} else if (event.key === 'Escape') {
													event.preventDefault();
													cancelRename();
												}
											}}
											on:blur={() => saveRename(item.id)}
										/>
										<span class="history-time">
											{item.time_range ? $i18n.t(item.time_range) : '刚刚更新'}
										</span>
										<span class="history-description">BioAgent 分析 · {item.id.slice(0, 8)}</span>
									</span>
								</div>
							{:else}
								<button type="button" class="history-main" on:click={() => selectHistory(item.id)}>
									<span class:active={isActiveChat} class="history-leading">
										{#if isActiveChat}
											<Spinner className="size-4" />
										{:else}
											<ChatBubbleDotted className="size-5" strokeWidth="1.6" />
										{/if}
									</span>
									<span class="history-copy">
										<span class="history-name">{item.title || '未命名分析'}</span>
										<span class="history-time">
											{item.time_range ? $i18n.t(item.time_range) : '刚刚更新'}
										</span>
										<span class="history-description">BioAgent 分析 · {item.id.slice(0, 8)}</span>
									</span>
								</button>
							{/if}
							<button
								type="button"
								class="history-rename-button"
								aria-label="重命名对话"
								disabled={renamingChatId === item.id}
								on:click|stopPropagation={() => startRename(item)}
							>
								{#if renamingChatId === item.id}
									<Spinner className="size-4" />
								{:else}
									<Settings className="size-4" strokeWidth="1.8" />
								{/if}
							</button>
						</div>
					{/each}

					{#if !allHistoryItemsLoaded}
						<Loader
							on:visible={() => {
								loadMoreHistory();
							}}
						>
							<div class="history-loader">
								<Spinner className="size-4" />
								<span>{historyListLoading ? '加载中' : '加载更早对话'}</span>
							</div>
						</Loader>
					{:else}
						<div class="history-end">
							{#if historySearchQuery}
								共 {analysisChats.length} 个结果
							{:else}
								已显示全部历史
							{/if}
						</div>
					{/if}
				{:else}
					<div class="history-empty">
						<Search className="size-6" strokeWidth="1.7" />
						<strong>{historySearchQuery ? '未找到对话' : '暂无分析对话'}</strong>
						<span>{historySearchQuery ? '换个关键词试试' : '新建对话后会显示在这里'}</span>
					</div>
				{/if}
			</div>
		</aside>

		<main class="chat-panel panel">
			<section class="context-band">
				<h2>{selectedAnalysisChat?.title ?? '新建分析对话'}</h2>
				<div class="routing-controls" aria-label="分析路由模式">
					<div class="routing-segments">
						{#each ROUTING_MODES as mode}
							<button
								type="button"
								class:active={routingMode === mode}
								disabled={confirmingAnalysis || Boolean(pendingProposal)}
								on:click={() => {
									routingMode = mode;
									lastPlanControlKey = '';
								}}
							>
								{ROUTING_LABELS[mode as RoutingMode]}
							</button>
						{/each}
					</div>
				</div>
			</section>

			<section class="planning-controls" aria-label="分析目标与病毒类型">
				<div class="goal-control-heading">
					<div>
						<h3>分析目标</h3>
						<span
							>{selectedGoals.length ? `已选择 ${selectedGoals.length} 项` : '请选择至少一项'}</span
						>
						<button
							type="button"
							class="secondary-action"
							disabled={confirmingAnalysis || Boolean(pendingProposal)}
							on:click={() => {
								selectedGoals = [...FIRST_WAVE_GOALS];
								lastPlanControlKey = '';
							}}
						>第一波 W1–W4+W6</button>
					</div>
					<div class="viral-type-control" aria-label="病毒类型">
						<span>病毒类型</span>
						{#each VIRAL_TYPES as value}
							<button
								type="button"
								class:active={viralType === value}
								disabled={confirmingAnalysis || Boolean(pendingProposal)}
								on:click={() => {
									viralType = value;
									lastPlanControlKey = '';
								}}>{value}</button
							>
						{/each}
					</div>
				</div>
				<div class="goal-grid">
					{#each ANALYSIS_GOALS as goal}
						<button
							type="button"
							class:active={selectedGoals.includes(goal.id)}
							disabled={confirmingAnalysis || Boolean(pendingProposal)}
							on:click={() => toggleGoal(goal.id)}
						>
							<strong>{goal.label}</strong>
							<span>{goal.description}</span>
						</button>
					{/each}
				</div>
				{#if plannerBusy}
					<p class="planner-state"><Spinner className="size-4" /> 正在生成确定性方案…</p>
				{:else if plannerError && !(plannerErrorCode === 'PLANNER_UNAVAILABLE' && analysisHealthState?.deterministic.status === 'unavailable')}
					<p class="planner-state error-text">{plannerError}</p>
				{/if}
			</section>
			{#if analysisHealthState?.deterministic.status === 'unavailable'}
				<div class="service-banner">
					确定性规划服务不可用，请确认 BioAgent 分析服务已启动后重试。
				</div>
			{/if}
			{#if analysisHealthState?.conversation_model.status === 'unavailable'}
				<div class="service-banner">
					对话模型当前不可用；数据集、确定性方案、执行和报告仍可正常使用。
				</div>
			{/if}
			<div class="service-banner">
				第一波：W2 使用 workflow2_virusid；注释流程为 W6，RNA 专项为 RVA；定种为 virus_taxonomy。只读查询不启动计算。
			</div>
			{#if pendingProposal}
				<section class="proposal-card" aria-label="方案修改提案">
					<div>
						<strong>待确认的方案修改</strong>
						<span>基于 revision {pendingProposal.base_plan_revision}</span>
					</div>
					{#if pendingProposal.patch.goals}
						<p>
							分析目标：{selectedGoals
								.map((id) => ANALYSIS_GOALS.find((goal) => goal.id === id)?.label ?? id)
								.join('、')} → {pendingProposal.patch.goals
								.map((id) => ANALYSIS_GOALS.find((goal) => goal.id === id)?.label ?? id)
								.join('、')}
						</p>
					{/if}
					{#if pendingProposal.patch.viral_type}
						<p>病毒类型：{viralType} → {pendingProposal.patch.viral_type}</p>
					{/if}
					<div class="action-row">
						<button
							class="primary-action"
							type="button"
							disabled={proposalBusy}
							on:click={acceptProposal}>接受并重编方案</button
						>
						<button
							class="secondary-action"
							type="button"
							disabled={proposalBusy}
							on:click={rejectProposal}>拒绝</button
						>
					</div>
				</section>
			{/if}
			{#if proposalError}<p class="planner-state error-text">{proposalError}</p>{/if}

			<div class="messages-viewport" bind:this={messageViewport}>
				{#each visibleLiveMessages as message (message.id)}
					<article
						class:error-message={Boolean(message.error)}
						class={`message-row ${message.role}`}
					>
						<div class="avatar" aria-hidden="true">
							{#if message.role === 'user'}
								<UserCircle className="size-7" strokeWidth="1.7" />
							{:else}
								<Sparkles className="size-6" strokeWidth="1.8" />
							{/if}
						</div>
						<div class="message-bubble">
							{#if message.content}
								{#if message.role === 'assistant'}
									<BioAgentMarkdown
										id={`analysis-bioagent-${message.id}`}
										content={message.content}
										done={message.done ?? false}
										model={$analysisChatState.model}
										variant="analysis"
									/>
								{:else}
									<p>{message.content}</p>
								{/if}
							{:else if message.status}
								<p class="muted">{message.status}</p>
							{:else if message.done === false}
								<p class="typing" aria-label="正在生成回复">
									<span></span><span></span><span></span>
								</p>
							{/if}

							{#if message.error}
								<p class="error-text">{message.error}</p>
							{:else if message.status && message.content}
								<div class="message-time">{message.status}</div>
							{:else}
								<div class="message-time">{getMessageTime(message.timestamp)}</div>
							{/if}
						</div>
					</article>
				{/each}
				{#if deterministicPlan && selectedGoals.length > 0}
					{@const deterministicResource = getResourceEstimate(activeAnalysisPlan)}
					{@const deterministicRows = buildAnalysisStageRows(
						getDisplayedPipelineSteps(activeAnalysisPlan as AnalysisPlanOutputItem)
					)}
					<article class="message-row planner">
						<div class="avatar" aria-hidden="true">
							<CheckCircle className="size-6" strokeWidth="1.8" />
						</div>
						<div class="message-bubble planner-bubble">
							<div class="analysis-card">
								<div class="card-heading">
									<div>
										<h3>{deterministicPlan.title}</h3>
										<p>{deterministicPlan.summary}</p>
									</div>
									<span class="route-mode-badge"
										>{ROUTING_LABELS[
											(deterministicPlan.routing?.requested_mode ?? 'auto') as RoutingMode
										]} · revision {deterministicPlan.revision}</span
									>
								</div>
								{#if deterministicPlan.routing}
									<div class="adaptive-route-map">
										{#if deterministicPlan.routing.adaptive}
											<div class="route-node">5% 快速初筛</div>
											<span>→</span>
										{/if}
										<div class="route-outcome">
											{deterministicRoutingSummary(
												deterministicPlan.routing as AnalysisPlanRouting
											)}
										</div>
									</div>
								{/if}
								{#if !goalsPlanCurrent || plannerBusy}
									<p class="planner-state">方案流程图尚未跟上当前勾选（定量/注释等），正在重编…</p>
								{/if}
								<div class="pipeline-map" class:pipeline-stale={!goalsPlanCurrent || plannerBusy}>
									{#each deterministicRows as row}
										<div class="pipeline-row">
											{#each row as step}
												<div class="pipeline-step tone-cyan">
													<strong>{step.label}</strong>
													{#if step.is_deliverable}<span class="stage-deliverable">交付结果</span
														>{/if}
												</div>
											{/each}
										</div>
									{/each}
								</div>
							</div>
							<div class="resource-card compact-resource-card">
								<h3>资源估算</h3>
								<div class="resource-summary">
									<div class="resource-item">
										<span>预计耗时 P90</span><strong
											>{formatResourceDuration(
												deterministicResource?.duration_seconds.p90 ?? null
											)}</strong
										>
									</div>
									<div class="resource-item">
										<span>建议内存</span><strong
											>{formatResourceMemory(
												deterministicResource?.peak_memory_mb.reserve ?? null
											)}</strong
										>
									</div>
									<div class="resource-item">
										<span>可信度</span><strong
											>{deterministicResource
												? resourceConfidenceLabels[deterministicResource.confidence]
												: '待估算'}</strong
										>
									</div>
								</div>
								{#if deterministicPlan.blocking_reason}<p class="plan-blocking-reason">
										{deterministicPlan.blocking_reason}
									</p>{/if}
								{#if deterministicPlan.execution}
									<p class="planner-state">分析任务已确认：{deterministicPlan.execution.status}</p>
								{:else}
									{#if !canConfirmCurrentPlan && confirmBlockReason}
										<p class="plan-blocking-reason">{confirmBlockReason}</p>
									{/if}
									<div class="action-row">
										<button
											type="button"
											class="primary-action"
											disabled={!canConfirmCurrentPlan}
											on:click={confirmAnalysis}
											><Bolt className="size-5" strokeWidth="1.8" /><span
												>{confirmingAnalysis ? '正在启动…' : '确认启动分析'}</span
											></button
										>
										<button type="button" class="secondary-action" on:click={adjustRequirements}
											><Settings className="size-5" strokeWidth="1.8" /><span>咨询方案</span
											></button
										>
									</div>
								{/if}
							</div>
						</div>
					</article>
				{/if}
				{#if $analysisChatState.error && !hasLiveMessageError}
					<div class="live-chat-error">{$analysisChatState.error}</div>
				{/if}
			</div>

			<form class="composer" on:submit|preventDefault={submitDraft}>
				<textarea
					bind:this={draftInput}
					bind:value={draft}
					rows="3"
					placeholder={$analysisChatState.loadingModel
						? '正在连接 BioAgent...'
						: '询问当前数据集或方案，或描述希望调整的分析目标...'}
					disabled={$analysisChatState.loadingModel}
					on:keydown={(event) => {
						if (event.isComposing || event.keyCode === 229) return;

						if (event.key === 'Enter' && !event.shiftKey) {
							event.preventDefault();
							submitDraft();
						}
					}}
				></textarea>
				<div class="composer-toolbar">
					<div class="composer-tools">
						<button type="button" on:click={() => (rightMode = 'files')}>
							<Search className="size-5" strokeWidth="1.8" />
							<span>选择文件</span>
						</button>
					</div>
					<div class="composer-actions">
						<button type="button" class="attach-button" on:click={() => (rightMode = 'files')}>
							<Clip className="size-5" strokeWidth="1.8" />
						</button>
						{#if $analysisChatState.generating}
							<button
								type="button"
								class="send-button stop-button"
								aria-label="停止生成"
								on:click={analysisChat.stop}
							>
								<XMark className="size-6" strokeWidth="1.8" />
							</button>
						{:else}
							<button
								type="submit"
								class="send-button"
								aria-label="发送"
								disabled={$analysisChatState.loadingModel || !draft.trim()}
							>
								<ArrowUpCircle className="size-7" strokeWidth="1.8" />
							</button>
						{/if}
					</div>
				</div>
			</form>
		</main>

		<aside class="right-panel panel">
			<div class="right-tabs">
				<button
					type="button"
					class:active={rightMode === 'status'}
					on:click={() => (rightMode = 'status')}
				>
					系统状态
				</button>
				<button
					type="button"
					class:active={rightMode === 'files'}
					on:click={() => (rightMode = 'files')}
				>
					文件列表
				</button>
				<button
					type="button"
					class:active={rightMode === 'knowledge'}
					on:click={() => (rightMode = 'knowledge')}
				>
					知识/专项
				</button>
				<button
					type="button"
					class:active={rightMode === 'ops'}
					on:click={() => (rightMode = 'ops')}
				>
					治理
				</button>
			</div>

			{#if rightMode === 'status'}
				<div class="right-scroll">
					<section class="right-section">
						<div class="section-heading">
							<h3>当前任务</h3>
							<span>{analysisRunStatusLabel}</span>
						</div>
						<div class="task-list">
							{#if analysisRunStatusError}
								<div class="task-empty">
									<XMark className="size-5" strokeWidth="1.8" />
									<span>{analysisRunStatusError}</span>
								</div>
							{:else if analysisRunStatusLoading && analysisRunTasks.length === 0}
								<div class="task-empty">
									<Spinner className="size-4" />
									<span>读取分析任务</span>
								</div>
							{:else if analysisRunTasks.length === 0}
								<div class="task-empty">
									<Search className="size-5" strokeWidth="1.8" />
									<span>暂无任务</span>
								</div>
							{/if}
							{#each analysisRunTasks as task}
								<div class="task-card">
									<div class="task-meta">
										<strong>{task.sample}</strong>
										<span>{task.stage}</span>
										<em>{analysisRunStepText || `${task.progress}%`}</em>
									</div>
									<div class="progress-track">
										<div
											class={`progress-fill ${toneClass(task.tone)}`}
											style={`--progress: ${task.progress}%`}
										></div>
									</div>
								</div>
							{/each}
						</div>
						{#if analysisRunStatus?.routing}
							<div class="routing-status-card">
								<div>
									<span>自适应路由</span>
									<strong>{routingPhaseLabel(analysisRunStatus.routing.phase)}</strong>
								</div>
								{#if analysisRunStatus.routing.decision?.selected_route}
									<div>
										<span>选择路径</span>
										<strong>路径 {analysisRunStatus.routing.decision.selected_route}</strong>
									</div>
								{/if}
								{#if analysisRunStatus.routing.decision?.confidence}
									<div>
										<span>初筛置信度</span>
										<strong
											>{analysisRunStatus.routing.decision.confidence === 'high'
												? '高'
												: '低'}</strong
										>
									</div>
								{/if}
							</div>
						{/if}
						{#if analysisRunStatus?.report_available}
							<button
								type="button"
								class="internal-report-button"
								disabled={downloadingCurrentReport}
								on:click={downloadCurrentDiagnosticReport}
							>
								{#if downloadingCurrentReport}
									<Spinner className="size-4" />
									<span>生成下载</span>
								{:else}
									<span
										>{analysisRunStatus.routing?.decision?.report_kind === 'preliminary_screen' ||
										analysisRunStatus.routing?.decision?.selected_route === 'A'
											? '下载初筛报告'
											: '下载诊断意见书'}</span
									>
								{/if}
							</button>
							{#if currentReportDownloadError}
								<p class="internal-report-error">{currentReportDownloadError}</p>
							{/if}
						{/if}
						{#if analysisRunStatus?.internal_report_available}
							<button
								type="button"
								class="internal-report-button"
								disabled={downloadingInternalReport}
								on:click={downloadInternalReport}
							>
								{#if downloadingInternalReport}
									<Spinner className="size-4" />
									<span>生成下载</span>
								{:else}
									<span>下载内部技术报告</span>
								{/if}
							</button>
							{#if internalReportDownloadError}
								<p class="internal-report-error">{internalReportDownloadError}</p>
							{/if}
						{/if}
					</section>

					<section class="right-section">
						<div class="section-heading">
							<h3>资源使用</h3>
							<span>{resourceStatusLabel}</span>
						</div>
						<div class="resource-list">
							{#each systemResourceItems as resource}
								<div class="resource-line">
									<div class={`resource-icon ${toneClass(resource.tone)}`}>
										<Database className="size-5" strokeWidth="1.8" />
									</div>
									<div class="resource-line-main">
										<div class="resource-line-heading">
											<strong>{resource.label}</strong>
											<div class="resource-stats">
												<span>{resource.value}</span>
												<em>{resource.progress}%</em>
											</div>
										</div>
										<div class="progress-track">
											<div
												class={`progress-fill ${toneClass(resource.tone)}`}
												style={`--progress: ${resource.progress}%`}
											></div>
										</div>
									</div>
								</div>
							{/each}
						</div>
					</section>
				</div>
			{:else if rightMode === 'knowledge'}
				<div class="right-scroll">
					<AnalysisKnowledgePanel />
				</div>
			{:else if rightMode === 'ops'}
				<div class="right-scroll">
					<AnalysisOpsPanel />
				</div>
			{:else}
				<div class="right-scroll files-scroll">
					{#if activeDataset}
						<AnalysisDatasetCard
							dataset={activeDataset}
							catalog={datasetCatalog}
							saving={datasetBusy}
							on:save={(event) => saveDatasetRevision(event.detail.artifacts)}
							on:replan={replanDataset}
						/>
					{/if}
					{#if datasetError}<p class="live-chat-error">{datasetError}</p>{/if}
					<AnalysisFileTree
						bind:selectedPaths={selectedAnalysisFilePaths}
						on:apply={(event) => createDatasetFromSelection(event.detail.paths)}
					/>
				</div>
			{/if}
		</aside>
	</div>
</div>

<style>
	:global(html.dark) .analysis-page,
	.analysis-page {
		color-scheme: dark;
	}

	.analysis-page {
		min-height: 100vh;
		max-height: 100dvh;
		overflow: hidden;
		background:
			linear-gradient(rgba(18, 41, 60, 0.18) 1px, transparent 1px),
			linear-gradient(90deg, rgba(18, 41, 60, 0.18) 1px, transparent 1px),
			linear-gradient(135deg, #020712 0%, #061321 44%, #03101b 100%);
		background-size:
			42px 42px,
			42px 42px,
			auto;
		color: #e7f7ff;
		font-family: Inter, 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
	}

	button,
	a,
	textarea,
	input {
		font: inherit;
		letter-spacing: 0;
	}

	button {
		cursor: pointer;
	}

	.analysis-header {
		height: 66px;
		display: grid;
		grid-template-columns: minmax(260px, 320px) minmax(280px, 1fr) minmax(320px, auto);
		align-items: center;
		gap: 18px;
		padding: 10px 18px 8px;
		border-bottom: 1px solid rgba(100, 180, 220, 0.22);
		background: rgba(2, 9, 18, 0.78);
		backdrop-filter: blur(18px);
	}

	.header-title,
	.header-actions,
	.user-button,
	.panel-title-row,
	.history-item,
	.history-main,
	.card-heading,
	.action-row,
	.section-heading,
	.resource-line,
	.composer-toolbar {
		display: flex;
		align-items: center;
	}

	.header-title p,
	.history-time,
	.history-description,
	.message-time,
	.section-heading span {
		color: rgba(204, 231, 244, 0.62);
	}

	.header-title {
		justify-content: center;
		gap: 12px;
		min-width: 0;
		color: #27d9ff;
	}

	.header-title h1 {
		margin: 0;
		color: #f4fbff;
		font-size: 22px;
		line-height: 1.1;
		font-weight: 750;
	}

	.header-title p {
		margin: 4px 0 0;
		font-size: 12px;
	}

	.header-actions {
		justify-content: flex-end;
		gap: 10px;
	}

	.header-link,
	.icon-button,
	.panel-icon-button,
	.user-button {
		border: 1px solid rgba(111, 178, 218, 0.22);
		background: rgba(8, 26, 43, 0.74);
		color: #dff6ff;
		transition:
			border-color 0.18s ease,
			background 0.18s ease,
			color 0.18s ease;
	}

	.header-link {
		border-radius: 8px;
		padding: 8px 12px;
		text-decoration: none;
		font-size: 13px;
	}

	.icon-button,
	.panel-icon-button {
		width: 36px;
		height: 36px;
		display: grid;
		place-items: center;
		border-radius: 8px;
	}

	.user-button {
		gap: 8px;
		min-width: 178px;
		justify-content: center;
		border-radius: 8px;
		padding: 6px 10px;
	}

	.header-link:hover,
	.icon-button:hover,
	.panel-icon-button:hover,
	.panel-icon-button.active,
	.user-button:hover {
		border-color: rgba(34, 211, 238, 0.58);
		background: rgba(17, 60, 84, 0.78);
	}

	.analysis-grid {
		height: calc(100dvh - 66px);
		display: grid;
		grid-template-columns: 310px minmax(520px, 1fr) minmax(330px, 404px);
		gap: 10px;
		padding: 10px;
	}

	.panel {
		min-height: 0;
		border: 1px solid rgba(104, 169, 209, 0.38);
		border-radius: 8px;
		background:
			linear-gradient(180deg, rgba(12, 34, 54, 0.92), rgba(4, 18, 31, 0.94)), rgba(5, 18, 30, 0.94);
		box-shadow:
			inset 0 0 28px rgba(45, 147, 203, 0.1),
			0 18px 46px rgba(0, 0, 0, 0.24);
	}

	.history-panel,
	.chat-panel,
	.right-panel {
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.history-panel {
		padding: 12px;
	}

	.new-chat-button {
		height: 42px;
		border: 1px solid rgba(34, 211, 238, 0.8);
		border-radius: 8px;
		background: rgba(21, 173, 198, 0.34);
		color: #eaffff;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 9px;
		font-size: 15px;
	}

	.new-chat-button:hover,
	.new-chat-button.active {
		border-color: rgba(112, 240, 255, 0.92);
		background: rgba(25, 198, 220, 0.44);
	}

	.panel-title-row {
		justify-content: space-between;
		margin: 18px 2px 10px;
	}

	.panel-title-row h2,
	.context-band h2,
	.section-heading h3 {
		margin: 0;
		color: #f3fbff;
		font-weight: 750;
	}

	.panel-title-row h2 {
		font-size: 17px;
	}

	.history-search {
		height: 38px;
		display: flex;
		align-items: center;
		gap: 8px;
		margin: -2px 0 10px;
		border: 1px solid rgba(95, 167, 207, 0.28);
		border-radius: 8px;
		background: rgba(5, 20, 33, 0.78);
		color: rgba(207, 235, 247, 0.72);
		padding: 0 8px 0 10px;
	}

	.history-search input {
		min-width: 0;
		flex: 1;
		border: 0;
		outline: 0;
		background: transparent;
		color: #e8f8ff;
		font-size: 13px;
	}

	.history-search input::placeholder {
		color: rgba(207, 235, 247, 0.48);
	}

	.history-search input::-webkit-search-cancel-button {
		display: none;
	}

	.history-search button {
		width: 26px;
		height: 26px;
		display: grid;
		place-items: center;
		border: 0;
		border-radius: 6px;
		background: rgba(77, 126, 160, 0.18);
		color: #d8f4ff;
	}

	.history-list {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		overflow-y: auto;
		padding-right: 2px;
	}

	.history-item {
		position: relative;
		width: 100%;
		gap: 10px;
		border: 0;
		border-bottom: 1px solid rgba(111, 178, 218, 0.14);
		background: transparent;
		color: #d8eef8;
		padding: 0 7px 0 8px;
		text-align: left;
	}

	.history-main {
		min-width: 0;
		flex: 1;
		gap: 10px;
		border: 0;
		background: transparent;
		color: inherit;
		padding: 12px 0;
		text-align: left;
	}

	.history-main.editing {
		cursor: default;
	}

	.history-item::before {
		content: '';
		position: absolute;
		inset: 0 auto 0 0;
		width: 3px;
		border-radius: 99px;
		background: transparent;
	}

	.history-item.selected {
		background: rgba(22, 86, 122, 0.28);
	}

	.history-item.selected::before {
		background: #25d8ef;
		box-shadow: 0 0 16px rgba(37, 216, 239, 0.8);
	}

	.history-leading {
		flex: 0 0 auto;
		width: 20px;
		height: 20px;
		display: grid;
		place-items: center;
		color: #b6d8e8;
	}

	.history-leading.active {
		color: #25d8ef;
	}

	.history-copy {
		min-width: 0;
		flex: 1;
		display: grid;
		gap: 5px;
	}

	.history-name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 14px;
	}

	.history-title-input {
		width: 100%;
		min-width: 0;
		border: 1px solid rgba(34, 211, 238, 0.5);
		border-radius: 6px;
		background: rgba(5, 20, 33, 0.9);
		color: #eaffff;
		outline: 0;
		padding: 5px 7px;
		font-size: 14px;
	}

	.history-rename-button {
		width: 30px;
		height: 30px;
		flex: 0 0 auto;
		display: grid;
		place-items: center;
		border: 1px solid rgba(111, 178, 218, 0.18);
		border-radius: 7px;
		background: rgba(8, 26, 43, 0.36);
		color: rgba(213, 239, 250, 0.7);
		opacity: 0;
		transition:
			opacity 0.16s ease,
			border-color 0.16s ease,
			background 0.16s ease;
	}

	.history-item:hover .history-rename-button,
	.history-rename-button:focus-visible,
	.history-item.selected .history-rename-button {
		opacity: 1;
	}

	.history-rename-button:hover:not(:disabled) {
		border-color: rgba(34, 211, 238, 0.52);
		background: rgba(20, 81, 112, 0.52);
		color: #eaffff;
	}

	.history-time,
	.history-description {
		font-size: 12px;
	}

	.history-description {
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		overflow: hidden;
		line-height: 1.35;
	}

	.history-loader,
	.history-end {
		min-height: 48px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		color: rgba(210, 235, 246, 0.6);
		font-size: 12px;
	}

	.history-loader {
		border-bottom: 1px solid rgba(111, 178, 218, 0.12);
	}

	.history-empty {
		flex: 1;
		min-height: 220px;
		display: grid;
		place-items: center;
		align-content: center;
		gap: 8px;
		color: rgba(215, 239, 248, 0.62);
		text-align: center;
	}

	.history-empty strong {
		color: #edfaff;
		font-size: 14px;
	}

	.history-empty span {
		font-size: 12px;
	}

	.chat-panel {
		padding: 12px;
		gap: 10px;
	}

	.context-band {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		padding: 2px 4px 0;
	}

	.context-band h2 {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 17px;
		line-height: 1.25;
	}

	.planning-controls {
		display: grid;
		gap: 9px;
		padding: 11px;
		border: 1px solid rgba(88, 159, 196, 0.24);
		border-radius: 9px;
		background: rgba(5, 22, 36, 0.72);
	}

	.goal-control-heading,
	.viral-type-control {
		display: flex;
		align-items: center;
	}

	.goal-control-heading {
		justify-content: space-between;
		gap: 14px;
	}

	.goal-control-heading h3 {
		margin: 0 0 2px;
		font-size: 14px;
	}

	.goal-control-heading span,
	.goal-grid span {
		color: rgba(215, 239, 248, 0.62);
		font-size: 11px;
	}

	.viral-type-control {
		gap: 4px;
	}

	.viral-type-control > span {
		margin-right: 4px;
	}

	.viral-type-control button,
	.goal-grid button {
		border: 1px solid rgba(88, 159, 196, 0.26);
		background: rgba(8, 29, 46, 0.78);
		color: #dff7ff;
	}

	.viral-type-control button {
		padding: 5px 9px;
		border-radius: 6px;
		font-size: 11px;
	}

	.viral-type-control button.active,
	.goal-grid button.active {
		border-color: rgba(37, 225, 173, 0.72);
		background: rgba(13, 101, 82, 0.5);
	}

	.goal-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 7px;
	}

	.goal-grid button {
		display: grid;
		gap: 3px;
		padding: 8px 9px;
		border-radius: 7px;
		text-align: left;
	}

	.goal-grid strong {
		font-size: 12px;
	}

	.planner-state {
		display: flex;
		align-items: center;
		gap: 6px;
		margin: 0;
		font-size: 12px;
	}

	.service-banner,
	.proposal-card {
		margin: 0 1.15rem 0.75rem;
		border: 1px solid rgba(58, 161, 177, 0.2);
		border-radius: 0.8rem;
		background: rgba(237, 249, 251, 0.82);
		padding: 0.75rem 0.9rem;
		color: #365764;
		font-size: 0.82rem;
	}

	.proposal-card > div:first-child {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}

	.proposal-card p {
		margin: 0.55rem 0 0;
	}

	.routing-controls,
	.routing-segments {
		display: flex;
		align-items: center;
	}

	.routing-controls {
		gap: 10px;
	}

	.routing-segments {
		padding: 2px;
		border: 1px solid rgba(88, 159, 196, 0.28);
		border-radius: 8px;
		background: rgba(7, 24, 39, 0.75);
	}

	.routing-segments button,
	.apply-routing {
		border: 0;
		border-radius: 6px;
		background: transparent;
		color: rgba(221, 240, 248, 0.7);
		font-size: 12px;
	}

	.routing-segments button {
		min-width: 56px;
		padding: 7px 12px;
	}

	.routing-segments button.active {
		background: rgba(11, 109, 88, 0.72);
		box-shadow: inset 0 0 0 1px rgba(27, 227, 144, 0.72);
		color: #e9fff6;
	}

	.routing-segments button:disabled {
		cursor: not-allowed;
		opacity: 0.36;
	}

	.apply-routing {
		padding: 8px 10px;
		background: rgba(0, 177, 211, 0.14);
		box-shadow: inset 0 0 0 1px rgba(29, 214, 234, 0.46);
		color: #6eeaff;
	}

	.card-heading {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
	}

	.route-mode-badge {
		padding: 4px 9px;
		border: 1px solid rgba(31, 224, 147, 0.44);
		border-radius: 99px;
		background: rgba(10, 111, 83, 0.22);
		color: #63efb3;
		font-size: 11px;
	}

	.adaptive-route-map {
		display: grid;
		grid-template-columns: minmax(110px, auto) auto minmax(110px, auto) auto minmax(0, 1fr);
		align-items: center;
		gap: 9px;
		margin: 12px 0;
		color: #45dfff;
		font-size: 12px;
	}

	.route-node,
	.route-outcome {
		min-height: 42px;
		display: grid;
		place-items: center;
		padding: 8px 12px;
		border: 1px solid rgba(29, 214, 234, 0.46);
		border-radius: 7px;
		background: rgba(5, 40, 58, 0.62);
		text-align: center;
	}

	.route-outcome {
		border-color: rgba(31, 224, 147, 0.44);
		color: #80f3c1;
	}

	.messages-viewport {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		padding: 6px 2px 2px;
	}

	.message-row {
		display: grid;
		grid-template-columns: 44px minmax(0, 1fr);
		gap: 10px;
		margin-bottom: 18px;
	}

	.message-row.user {
		grid-template-columns: minmax(0, 1fr) 44px;
	}

	.message-row.user .avatar {
		grid-column: 2;
		grid-row: 1;
	}

	.message-row.user .message-bubble {
		grid-column: 1;
		justify-self: end;
		max-width: 64%;
		border-color: rgba(29, 214, 234, 0.58);
		background: rgba(4, 66, 91, 0.72);
	}

	.avatar {
		width: 42px;
		height: 42px;
		display: grid;
		place-items: center;
		border: 1px solid rgba(90, 177, 226, 0.36);
		border-radius: 50%;
		background: rgba(12, 38, 61, 0.82);
		color: #4bdcff;
	}

	.message-bubble {
		width: min(720px, 100%);
		border: 1px solid rgba(93, 159, 198, 0.34);
		border-radius: 8px;
		background: rgba(9, 26, 43, 0.84);
		padding: 15px 16px;
		color: #e9f8ff;
	}

	.message-bubble p {
		margin: 0;
		line-height: 1.75;
		font-size: 15px;
	}

	.message-bubble p.muted {
		color: rgba(219, 241, 250, 0.68);
	}

	.error-message .message-bubble {
		border-color: rgba(255, 92, 92, 0.46);
	}

	.error-text,
	.live-chat-error {
		color: #ffd4d4;
	}

	.error-text {
		margin-top: 8px !important;
		border: 1px solid rgba(255, 92, 92, 0.28);
		border-radius: 8px;
		padding: 8px 10px;
		background: rgba(95, 21, 30, 0.48);
	}

	.live-chat-error {
		margin: 0 0 16px 52px;
		border: 1px solid rgba(255, 92, 92, 0.34);
		border-radius: 8px;
		padding: 9px 11px;
		background: rgba(76, 16, 26, 0.46);
		font-size: 13px;
	}

	.typing {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		min-width: 54px;
		min-height: 28px;
	}

	.typing span {
		width: 6px;
		height: 6px;
		border-radius: 999px;
		background: #96f4ff;
		animation: typing-pulse 1s ease-in-out infinite;
	}

	.typing span:nth-child(2) {
		animation-delay: 0.12s;
	}

	.typing span:nth-child(3) {
		animation-delay: 0.24s;
	}

	.message-time {
		margin-top: 6px;
		text-align: right;
		font-size: 12px;
	}

	.analysis-card,
	.resource-card {
		margin-top: 14px;
		border: 1px solid rgba(32, 211, 238, 0.48);
		border-radius: 8px;
		background: rgba(4, 20, 34, 0.72);
	}

	.message-row.planner .avatar {
		color: #65efb5;
	}

	.planner-bubble {
		max-width: min(920px, calc(100% - 12px));
	}

	.card-heading p {
		margin: 4px 0 0;
		color: rgba(215, 239, 248, 0.66);
		font-size: 12px;
	}

	.compact-resource-card .resource-item {
		min-height: 70px;
	}

	.card-heading {
		justify-content: space-between;
		gap: 12px;
		padding: 12px 14px 10px;
		border-bottom: 1px solid rgba(92, 168, 210, 0.18);
	}

	.card-heading h3,
	.resource-card h3 {
		margin: 0;
		font-size: 16px;
		color: #f5fbff;
	}

	.pipeline-map {
		--pipeline-gap: 8px;
		display: grid;
		row-gap: var(--pipeline-gap);
		padding: 18px 28px 20px;
		align-items: center;
	}

	.pipeline-row {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
		column-gap: var(--pipeline-gap);
		align-items: center;
		width: 100%;
	}

	.pipeline-step {
		min-width: 0;
		min-height: 68px;
		display: grid;
		place-items: center;
		gap: 3px;
		padding: 7px;
		border: 1px solid;
		border-radius: 7px;
		background: rgba(8, 27, 43, 0.86);
		text-align: center;
	}

	.arrow-cell {
		display: grid;
		place-items: center;
		align-self: center;
		color: #25e7f5;
		font-size: 22px;
		line-height: 1;
		text-shadow: 0 0 8px rgba(37, 231, 245, 0.42);
	}

	.turn-cell {
		position: relative;
		width: 100%;
		height: 24px;
		color: #25e7f5;
		pointer-events: none;
		filter: drop-shadow(0 0 8px rgba(37, 231, 245, 0.42));
	}

	.turn-stem,
	.turn-line {
		position: absolute;
		background: currentColor;
	}

	.turn-stem {
		width: 2px;
		height: 18px;
		border-radius: 999px;
	}

	.turn-stem.start {
		top: 0;
		left: 50%;
		transform: translateX(-50%);
	}

	.turn-line {
		display: none;
	}

	.turn-stem.end {
		display: none;
	}

	.turn-head {
		position: absolute;
		left: 50%;
		bottom: 0;
		width: 0;
		height: 0;
		border-left: 5px solid transparent;
		border-right: 5px solid transparent;
		border-top: 7px solid currentColor;
		transform: translateX(-50%);
	}

	.pipeline-step strong {
		font-size: 13px;
	}

	.pipeline-step span {
		color: rgba(225, 241, 248, 0.7);
		font-size: 12px;
	}

	.tone-cyan {
		border-color: #15d7f1;
		color: #25e7f5;
	}

	.tone-green {
		border-color: #28e081;
		color: #67ffad;
	}

	.tone-amber {
		border-color: #ffc533;
		color: #ffe38f;
	}

	.tone-red {
		border-color: #ff5151;
		color: #ffb3b3;
	}

	.tone-neutral {
		border-color: rgba(148, 180, 202, 0.42);
		color: rgba(202, 225, 238, 0.72);
	}

	.resource-card {
		padding: 13px 14px 14px;
	}

	.resource-summary {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 10px;
		margin-top: 12px;
	}

	.resource-item {
		min-width: 0;
		display: grid;
		align-content: start;
		gap: 6px;
		border-right: 1px solid rgba(99, 162, 198, 0.22);
		padding: 6px 8px;
		color: #29e4f5;
	}

	.resource-item:last-child {
		border-right: 0;
	}

	.resource-item-heading {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: 28px;
	}

	.resource-summary span {
		color: rgba(221, 239, 247, 0.7);
		font-size: 13px;
	}

	.resource-summary strong {
		min-width: 0;
		overflow-wrap: anywhere;
		font-size: 17px;
		line-height: 1.3;
	}

	.resource-values {
		display: grid;
		gap: 3px;
	}

	.resource-values span,
	.resource-basis {
		line-height: 1.45;
	}

	.resource-warning {
		margin: 10px 8px 0;
		border-left: 2px solid rgba(255, 197, 51, 0.72);
		padding-left: 9px;
		color: #ffe09a;
		font-size: 12px;
		line-height: 1.5;
	}

	.pipeline-stale {
		opacity: 0.55;
	}
	.plan-blocking-reason {
		margin: 10px 8px 0;
		color: #ffb4aa;
		font-size: 12px;
		line-height: 1.5;
	}

	.action-row {
		gap: 12px;
		margin-top: 14px;
	}

	.primary-action,
	.secondary-action {
		height: 46px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 9px;
		border-radius: 8px;
		font-size: 15px;
	}

	.primary-action {
		flex: 1;
		border: 1px solid rgba(39, 255, 128, 0.72);
		background: rgba(30, 153, 78, 0.55);
		color: #ecfff4;
	}

	.secondary-action {
		flex: 0 0 240px;
		border: 1px solid rgba(35, 213, 244, 0.66);
		background: rgba(8, 42, 61, 0.74);
		color: #dffaff;
	}

	.primary-action:disabled,
	.secondary-action:disabled {
		cursor: not-allowed;
		opacity: 0.52;
	}

	.composer {
		border: 1px solid rgba(99, 163, 200, 0.42);
		border-radius: 8px;
		background: rgba(6, 19, 32, 0.88);
		padding: 12px;
	}

	.composer textarea {
		width: 100%;
		min-height: 62px;
		resize: none;
		border: 0;
		outline: 0;
		background: transparent;
		color: #eaf8ff;
		font-size: 15px;
		line-height: 1.55;
	}

	.composer textarea::placeholder {
		color: rgba(216, 236, 245, 0.58);
	}

	.composer textarea:disabled {
		cursor: wait;
		color: rgba(216, 240, 250, 0.5);
	}

	.composer-toolbar {
		justify-content: space-between;
		gap: 12px;
		margin-top: 8px;
	}

	.composer-tools,
	.composer-actions {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.composer-tools button,
	.attach-button,
	.send-button {
		border: 1px solid rgba(100, 159, 195, 0.34);
		border-radius: 8px;
		background: rgba(10, 31, 49, 0.88);
		color: #dff5ff;
	}

	.composer-tools button {
		height: 36px;
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 0 12px;
		font-size: 13px;
	}

	.attach-button,
	.send-button {
		width: 42px;
		height: 42px;
		display: grid;
		place-items: center;
	}

	.send-button {
		border-color: rgba(32, 211, 238, 0.72);
		background: rgba(15, 151, 183, 0.72);
		color: white;
	}

	.stop-button {
		border-color: rgba(255, 111, 111, 0.72);
		background: rgba(156, 45, 58, 0.72);
	}

	.send-button:disabled {
		cursor: not-allowed;
		opacity: 0.48;
	}

	.right-panel {
		padding: 12px;
	}

	.right-tabs {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
		margin-bottom: 10px;
	}

	.right-tabs button {
		height: 36px;
		border: 1px solid rgba(100, 160, 196, 0.28);
		border-radius: 8px;
		background: rgba(8, 28, 45, 0.78);
		color: rgba(223, 245, 255, 0.72);
	}

	.right-tabs button.active {
		border-color: rgba(34, 211, 238, 0.7);
		background: rgba(13, 104, 134, 0.5);
		color: white;
	}

	.right-scroll {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		padding-right: 2px;
	}

	.files-scroll {
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.right-section {
		border: 1px solid rgba(100, 160, 196, 0.24);
		border-radius: 8px;
		background: rgba(4, 19, 31, 0.7);
		padding: 13px;
		margin-bottom: 12px;
	}

	.section-heading {
		justify-content: space-between;
		gap: 10px;
		margin-bottom: 12px;
	}

	.section-heading h3 {
		font-size: 16px;
	}

	.task-list,
	.resource-list {
		display: grid;
		gap: 10px;
	}

	.task-empty {
		min-height: 72px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		border: 1px dashed rgba(103, 159, 194, 0.24);
		border-radius: 8px;
		color: rgba(225, 241, 248, 0.62);
		font-size: 13px;
	}

	.task-card,
	.resource-line {
		border: 1px solid rgba(103, 159, 194, 0.22);
		border-radius: 8px;
		background: rgba(8, 27, 43, 0.74);
	}

	.task-card {
		padding: 11px 12px;
	}

	.task-meta {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto auto;
		gap: 10px;
		align-items: center;
		margin-bottom: 10px;
		font-size: 13px;
	}

	.task-meta strong {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: #edfaff;
	}

	.task-meta span,
	.task-meta em {
		color: rgba(225, 241, 248, 0.7);
		font-style: normal;
	}

	.internal-report-button {
		width: 100%;
		margin-top: 12px;
		padding: 9px 12px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		border: 1px solid rgba(39, 217, 255, 0.42);
		border-radius: 8px;
		background: rgba(39, 217, 255, 0.1);
		color: #a9efff;
	}

	.internal-report-button:disabled {
		cursor: wait;
		opacity: 0.65;
	}

	.internal-report-error {
		margin: 8px 0 0;
		color: #ff9c9c;
		font-size: 12px;
	}

	.routing-status-card {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 8px;
		margin-top: 10px;
		padding: 10px;
		border: 1px solid rgba(29, 214, 234, 0.22);
		border-radius: 8px;
		background: rgba(5, 30, 47, 0.58);
	}

	.routing-status-card div {
		display: grid;
		gap: 3px;
	}

	.routing-status-card span {
		color: rgba(215, 239, 248, 0.58);
		font-size: 10px;
	}

	.routing-status-card strong {
		color: #dff8ff;
		font-size: 12px;
	}

	.routing-status-card p {
		grid-column: 1 / -1;
		margin: 2px 0 0;
		color: #ffcb67;
		font-size: 11px;
	}

	.progress-track {
		height: 8px;
		border-radius: 99px;
		overflow: hidden;
		background: rgba(86, 111, 135, 0.42);
	}

	.progress-fill {
		width: var(--progress);
		height: 100%;
		border: 0;
		border-radius: inherit;
		background: currentColor;
	}

	.resource-line {
		gap: 10px;
		padding: 10px;
	}

	.resource-icon {
		width: 34px;
		height: 34px;
		display: grid;
		place-items: center;
		border: 1px solid;
		border-radius: 8px;
		background: rgba(4, 20, 34, 0.78);
	}

	.resource-line-main {
		min-width: 0;
		flex: 1;
		display: grid;
		gap: 8px;
	}

	.resource-line-heading {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 8px;
		align-items: center;
		font-size: 13px;
	}

	.resource-stats {
		min-width: 0;
		display: flex;
		align-items: baseline;
		justify-content: flex-end;
		gap: 8px;
		white-space: nowrap;
	}

	.resource-stats span {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.resource-stats span,
	.resource-stats em {
		color: rgba(225, 241, 248, 0.7);
		font-style: normal;
		font-size: 12px;
	}

	@keyframes typing-pulse {
		0%,
		80%,
		100% {
			opacity: 0.35;
			transform: translateY(0);
		}
		40% {
			opacity: 1;
			transform: translateY(-2px);
		}
	}

	@media (max-width: 1220px) {
		.analysis-header {
			grid-template-columns: minmax(220px, 1fr) auto;
		}

		.header-title {
			display: none;
		}

		.analysis-grid {
			grid-template-columns: 280px minmax(480px, 1fr);
		}

		.right-panel {
			display: none;
		}
	}

	@media (max-width: 900px) {
		.analysis-page {
			max-height: none;
			overflow: auto;
		}

		.analysis-header {
			height: auto;
			grid-template-columns: 1fr;
			align-items: start;
		}

		.header-actions {
			justify-content: flex-start;
			flex-wrap: wrap;
		}

		.analysis-grid {
			height: auto;
			grid-template-columns: 1fr;
		}

		.history-panel,
		.chat-panel {
			min-height: 0;
		}

		.history-panel {
			max-height: 420px;
		}

		.messages-viewport {
			min-height: 520px;
		}

		.composer-toolbar {
			flex-direction: column;
			align-items: stretch;
		}

		.resource-summary {
			min-width: 0;
			grid-template-columns: 1fr;
		}

		.message-row.user .message-bubble {
			max-width: 100%;
		}

		.context-band,
		.routing-controls {
			align-items: stretch;
			flex-direction: column;
		}

		.routing-segments {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.goal-control-heading {
			align-items: stretch;
			flex-direction: column;
		}

		.goal-grid {
			grid-template-columns: 1fr;
		}

		.adaptive-route-map {
			grid-template-columns: 1fr;
		}

		.adaptive-route-map > span {
			text-align: center;
			transform: rotate(90deg);
		}

		.pipeline-map,
		.pipeline-row {
			grid-template-columns: 1fr;
			gap: 10px;
		}

		.arrow-cell,
		.turn-cell {
			display: none;
		}

		.pipeline-step {
			width: 100%;
		}

		.secondary-action {
			flex-basis: auto;
		}
	}
</style>
