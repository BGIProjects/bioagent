from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from open_webui.models.chat_messages import ChatMessages
from open_webui.models.chats import Chats
from open_webui.socket.main import get_event_emitter

log = logging.getLogger(__name__)
TERMINAL_STATUSES = {'completed', 'failed', 'blocked'}
POLL_SECONDS = 5


def analysis_run_root() -> Path:
    return Path(
        os.getenv('BIOAGENT_RUN_ROOT')
        or os.getenv('ANALYSIS_FILE_ROOT', '/data/runs')
    ).resolve()


def _safe_state_path(value: str | Path) -> Path:
    path = Path(value).resolve()
    root = analysis_run_root()
    if path != root and root not in path.parents:
        raise ValueError('Analysis state is outside BIOAGENT_RUN_ROOT')
    return path


def _read_state(path: Path) -> dict[str, Any]:
    state = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(state, dict) or state.get('version') != 3:
        raise ValueError('Invalid analysis run state')
    return state


def _state_status(state: dict[str, Any]) -> str:
    execution = state.get('execution')
    if not isinstance(execution, dict):
        return 'running'
    return str(execution.get('status') or 'running')


def render_terminal_summary(state: dict[str, Any]) -> str:
    status = _state_status(state)
    execution = state.get('execution') if isinstance(state.get('execution'), dict) else {}
    title = state.get('title') or state.get('run_id') or '分析任务'
    run_dir = state.get('run_dir') or ''
    log_path = execution.get('log') or str(Path(run_dir) / '.bioagent' / 'execution.log')
    steps = state.get('steps') if isinstance(state.get('steps'), list) else []
    completed = sum(
        1 for step in steps if isinstance(step, dict) and step.get('status') == 'completed'
    )

    if status == 'completed':
        lines = [
            '## 分析完成',
            f'**{title}** 已完成。',
            f'- 步骤：{completed}/{len(steps)}',
            f'- 运行目录：`{run_dir}`',
            f'- 执行日志：`{log_path}`',
        ]
        report = state.get('report')
        if isinstance(report, dict) and report.get('available') is True:
            lines.append('- 诊断报告：已生成，可在分析状态区打开')
        return '\n\n'.join([lines[0], '\n'.join(lines[1:])])

    reason = execution.get('error') or execution.get('message')
    if not reason and isinstance(state.get('routing'), dict):
        reason = state['routing'].get('reason')
    reason = reason or ('流程已停止，等待补充输入。' if status == 'blocked' else '执行进程异常退出。')
    heading = '## 分析已阻止' if status == 'blocked' else '## 分析失败'
    return '\n\n'.join(
        [
            heading,
            '\n'.join(
                [
                    f'**{title}** 未能完成。',
                    f'- 原因：{reason}',
                    f'- 运行目录：`{run_dir}`',
                    f'- 执行日志：`{log_path}`',
                ]
            ),
        ]
    )


def _terminal_output(
    output: list[Any], state: dict[str, Any], summary: str
) -> list[Any]:
    run_id = state.get('run_id')
    status = _state_status(state)
    updated: list[Any] = []
    message_updated = False
    run_updated = False

    for item in output:
        if not isinstance(item, dict):
            updated.append(item)
            continue
        item = {**item}
        if item.get('type') == 'message' and not message_updated:
            item.update(
                {
                    'status': 'completed',
                    'role': 'assistant',
                    'content': [{'type': 'output_text', 'text': summary}],
                }
            )
            message_updated = True
        elif item.get('type') == 'analysis_run' and (
            not run_id or (item.get('run') or {}).get('run_id') == run_id
        ):
            item['status'] = status
            run_updated = True
        updated.append(item)

    if not message_updated:
        updated.insert(
            0,
            {
                'type': 'message',
                'id': f'msg_analysis_{run_id}',
                'status': 'completed',
                'role': 'assistant',
                'content': [{'type': 'output_text', 'text': summary}],
            },
        )
    if not run_updated:
        execution = state.get('execution') if isinstance(state.get('execution'), dict) else {}
        updated.append(
            {
                'type': 'analysis_run',
                'id': f'analysis_run_{run_id}',
                'status': status,
                'run': {
                    'run_id': run_id,
                    'run_dir': state.get('run_dir'),
                    'state_path': str(Path(state.get('run_dir') or '') / '.bioagent' / 'state.json'),
                    'log_path': execution.get('log'),
                },
            }
        )
    return updated


async def finalize_analysis_run(state_path: str | Path) -> bool:
    path = _safe_state_path(state_path)
    state = _read_state(path)
    if _state_status(state) not in TERMINAL_STATUSES:
        return False

    chat_id = state.get('openwebui_chat_id')
    message_id = state.get('assistant_message_id')
    if not isinstance(chat_id, str) or not isinstance(message_id, str):
        return False

    message = await Chats.get_message_by_id_and_message_id(chat_id, message_id)
    chat = await Chats.get_chat_by_id(chat_id)
    if not message or not chat:
        return False

    summary = render_terminal_summary(state)
    output = _terminal_output(message.get('output') or [], state, summary)
    update = {'content': summary, 'output': output, 'done': True}
    await Chats.upsert_message_to_chat_by_id_and_message_id(chat_id, message_id, update)

    emitter = await get_event_emitter(
        {'user_id': chat.user_id, 'chat_id': chat_id, 'message_id': message_id},
        update_db=False,
    )
    if emitter:
        await emitter({'type': 'chat:completion', 'data': update})
    return True


async def _watch(app, state_path: Path) -> None:
    while True:
        try:
            state = _read_state(state_path)
            if _state_status(state) in TERMINAL_STATUSES:
                await finalize_analysis_run(state_path)
                return
        except FileNotFoundError:
            log.warning('Analysis state disappeared: %s', state_path)
            return
        except (OSError, ValueError, json.JSONDecodeError) as error:
            log.warning('Unable to monitor analysis state %s: %s', state_path, error)
        await asyncio.sleep(POLL_SECONDS)


def register_analysis_run_monitor(app, item: dict[str, Any]) -> bool:
    run = item.get('run') if isinstance(item.get('run'), dict) else {}
    value = run.get('state_path')
    if not isinstance(value, str):
        return False
    try:
        state_path = _safe_state_path(value)
    except ValueError:
        return False

    monitors = getattr(app.state, 'analysis_run_monitors', None)
    if monitors is None:
        monitors = app.state.analysis_run_monitors = {}
    key = str(state_path)
    existing = monitors.get(key)
    if existing and not existing.done():
        return True
    task = asyncio.create_task(_watch(app, state_path))
    monitors[key] = task
    task.add_done_callback(lambda finished: monitors.pop(key, None))
    return True


async def recover_analysis_run_monitors(app) -> None:
    app.state.analysis_run_monitors = {}
    recoverable: set[tuple[str, str]] = set()
    root = analysis_run_root()
    if root.is_dir():
        for state_path in root.glob('analysis-*/.bioagent/state.json'):
            try:
                state = _read_state(state_path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            chat_id = state.get('openwebui_chat_id')
            message_id = state.get('assistant_message_id')
            if isinstance(chat_id, str) and isinstance(message_id, str):
                recoverable.add((chat_id, message_id))
                register_analysis_run_monitor(
                    app,
                    {
                        'run': {
                            'state_path': str(state_path),
                        }
                    },
                )

    for message in await ChatMessages.get_unfinished_assistant_messages():
        message_id = message.id.removeprefix(f'{message.chat_id}-')
        if (message.chat_id, message_id) in recoverable:
            continue
        text = '响应已中断，请重试。'
        await Chats.upsert_message_to_chat_by_id_and_message_id(
            message.chat_id,
            message_id,
            {
                'content': text,
                'done': True,
                'error': {'content': text},
            },
        )


async def stop_analysis_run_monitors(app) -> None:
    monitors = getattr(app.state, 'analysis_run_monitors', {})
    tasks = list(monitors.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    monitors.clear()
