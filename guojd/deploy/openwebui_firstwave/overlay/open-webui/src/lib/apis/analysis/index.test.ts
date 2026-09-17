import { afterEach, describe, expect, it, vi } from 'vitest';

import {
	AnalysisApiError,
	createAnalysisPlan,
	executeAnalysisPlan,
	registerAnalysisProposal
} from '.';

const response = (plan: Record<string, unknown>) =>
	Promise.resolve({
		ok: true,
		json: () => Promise.resolve({ chat_id: 'chat-1', plan })
	} as Response);

describe('deterministic analysis plan API', () => {
	afterEach(() => vi.unstubAllGlobals());

	it('serializes only dataset and authoritative controls', async () => {
		const fetch = vi.fn(() => response({ id: 'pl_test', revision: 1 }));
		vi.stubGlobal('fetch', fetch);

		await createAnalysisPlan('token', {
			dataset: { id: 'ds-test', revision: 2 },
			goals: ['virus_summary', 'microbe_summary'],
			options: { viral_type: 'RNA' },
			routing: { mode: 'emergency' }
		});

		const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
		const body = JSON.parse(String(init?.body));
		expect(String(url)).toMatch(/\/analysis\/plans$/);
		expect(body).toEqual({
			dataset: { id: 'ds-test', revision: 2 },
			goals: ['virus_summary', 'microbe_summary'],
			options: { viral_type: 'RNA' },
			routing: { mode: 'emergency' }
		});
		expect(body).not.toHaveProperty('prompt');
		expect(body).not.toHaveProperty('model');
	});

	it('confirms through the execute endpoint without a chat completion', async () => {
		const fetch = vi.fn(() => response({ id: 'pl_test', revision: 3 }));
		vi.stubGlobal('fetch', fetch);

		await executeAnalysisPlan('token', 'pl_test', 3);

		const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
		expect(String(url)).toMatch(/\/analysis\/plans\/pl_test\/revisions\/3\/execute$/);
		expect(String(url)).not.toContain('/chat/completions');
		expect(init?.method).toBe('POST');
		expect(init?.body).toBeUndefined();
	});

	it('registers only the whitelisted patch envelope', async () => {
		const fetch = vi.fn(() =>
			Promise.resolve({
				ok: true,
				json: () =>
					Promise.resolve({
						proposal: { id: 'pp_test', patch: { viral_type: 'RNA' }, status: 'pending' }
					})
			} as Response)
		);
		vi.stubGlobal('fetch', fetch);

		await registerAnalysisProposal('token', 'chat-1', {
			base_plan_revision: 4,
			patch: { viral_type: 'RNA' },
			model: 'MiniMax-M3'
		});

		const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
		expect(String(url)).toMatch(/\/analysis\/plans\/chat-1\/proposals$/);
		expect(JSON.parse(String(init.body))).toEqual({
			base_plan_revision: 4,
			patch: { viral_type: 'RNA' },
			model: 'MiniMax-M3'
		});
	});

	it('maps typed revision conflicts to a fixed recovery action', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(() =>
				Promise.resolve({
					ok: false,
					json: () =>
						Promise.resolve({
							detail: {
								code: 'PLAN_REVISION_CONFLICT',
								message: 'server text',
								context: {},
								retryable: false
							}
						})
				} as Response)
			)
		);

		const error = await createAnalysisPlan('token', {
			dataset: { id: 'ds-test', revision: 2 },
			goals: ['virus_summary'],
			options: { viral_type: 'RNA' },
			routing: { mode: 'standard' },
			base_plan_revision: 1
		}).catch((value) => value);

		expect(error).toBeInstanceOf(AnalysisApiError);
		expect(error.code).toBe('PLAN_REVISION_CONFLICT');
		expect(error.message).toBe('方案已有新版本，请重新加载当前对话后再操作。');
	});

	it('maps planner outages to a service startup action', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(() =>
				Promise.resolve({
					ok: false,
					json: () =>
						Promise.resolve({
							detail: {
								code: 'PLANNER_UNAVAILABLE',
								message: 'provider detail',
								context: {},
								retryable: true
							}
						})
				} as Response)
			)
		);

		const error = await createAnalysisPlan('token', {
			dataset: { id: 'ds-test', revision: 2 },
			goals: ['contig_filter'],
			options: { viral_type: 'RNA' },
			routing: { mode: 'standard' }
		}).catch((value) => value);

		expect(error).toBeInstanceOf(AnalysisApiError);
		expect(error.code).toBe('PLANNER_UNAVAILABLE');
		expect(error.message).toBe('无法连接 BioAgent 分析服务，请确认服务已启动后重试。');
	});
});
