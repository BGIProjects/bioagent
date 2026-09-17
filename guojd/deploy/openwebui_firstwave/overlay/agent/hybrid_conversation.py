"""Use MiniMax when available; fall back to local specialist conversation."""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import config
from conversation_events import OutputItemAdded, TextDelta
from local_conversation import LocalSessionManager

log = logging.getLogger(__name__)


class HybridSessionManager:
    def __init__(self) -> None:
        self._local = LocalSessionManager()
        self._remote: Any | None = None

    def _remote_manager(self) -> Any:
        if self._remote is None:
            from runtime import SessionManager

            self._remote = SessionManager()
        return self._remote

    def _use_remote(self) -> bool:
        return bool(config.MINIMAX_API_KEY) and not getattr(config, "USE_LOCAL_CONVERSATION", False)

    async def ensure_session(self, chat_id: str | None) -> None:
        if self._use_remote():
            try:
                await self._remote_manager().ensure_session(chat_id)
                return
            except Exception:
                log.exception("MiniMax ensure_session failed")
        await self._local.ensure_session(chat_id)

    async def close_all(self) -> None:
        if self._remote is not None:
            await self._remote.close_all()
        await self._local.close_all()

    async def stream_ephemeral_turn(self, messages: list[dict]) -> AsyncIterator[TextDelta | OutputItemAdded]:
        async for event in self.stream_turn(messages, None):
            yield event

    async def stream_turn(
        self,
        messages: list[dict],
        chat_id: str | None,
        routing_request: dict[str, Any] | None = None,
        dataset_context: dict[str, Any] | None = None,
        plan_context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[TextDelta | OutputItemAdded]:
        if self._use_remote():
            try:
                async for event in self._remote_manager().stream_turn(
                    messages,
                    chat_id,
                    routing_request,
                    dataset_context,
                    plan_context,
                    **kwargs,
                ):
                    yield event
                return
            except Exception:
                log.exception("MiniMax turn failed; using local specialist fallback")
                yield TextDelta("（MiniMax 暂时不可用，已改用本地方案编译。）\n")
        async for event in self._local.stream_turn(
            messages,
            chat_id,
            routing_request,
            dataset_context,
            plan_context,
            **kwargs,
        ):
            yield event
