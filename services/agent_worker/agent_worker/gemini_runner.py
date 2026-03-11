"""
GeminiRunner — spawns gemini-cli as a subprocess with --output-format stream-json.

Command built:
  gemini --prompt @/tmp/prompt_<id>.md \
         --output-format stream-json \
         --mcp-server <mcp_server_path> \
         --yolo
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field

from shared.config import settings
from shared.models.events import AgentRole
from services.agent_worker.agent_worker.event_emitter import EventEmitter
from services.agent_worker.agent_worker.stream_parser import NDJSONStreamParser, ParseResult

logger = logging.getLogger(__name__)


@dataclass
class GeminiResult:
    content: str
    total_tokens: int = 0
    tool_call_count: int = 0
    exit_code: int = 0
    stderr_output: str = ""


class GeminiRunner:
    def __init__(
        self,
        session_id: uuid.UUID,
        agent_id: str,
        agent_role: AgentRole,
        emitter: EventEmitter,
        mcp_server_path: str | None = None,
        model: str | None = None,
    ) -> None:
        self._session_id = session_id
        self._agent_id = agent_id
        self._agent_role = agent_role
        self._emitter = emitter
        self._mcp_server_path = mcp_server_path
        self._model = model or settings.gemini_model

    async def run(
        self,
        prompt: str,
        timeout: int = 300,
    ) -> GeminiResult:
        parser = NDJSONStreamParser(
            session_id=self._session_id,
            agent_id=self._agent_id,
            agent_role=self._agent_role,
            emitter=self._emitter,
            model=self._model,
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix=f"prompt_{self._agent_id}_", delete=False
        ) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            cmd = self._build_command(prompt_file)
            logger.info("Running gemini-cli: %s", " ".join(cmd[:4]))

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "GEMINI_API_KEY": settings.gemini_api_key},
            )

            stdout_task = asyncio.create_task(self._read_stdout(proc, parser))
            stderr_task = asyncio.create_task(self._read_stderr(proc))

            try:
                await asyncio.wait_for(
                    asyncio.gather(stdout_task, stderr_task, proc.wait()),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise TimeoutError(f"gemini-cli timed out after {timeout}s")

            stderr_output = stderr_task.result() if stderr_task.done() else ""
            return GeminiResult(
                content=parser.result.final_content,
                total_tokens=parser.result.total_tokens,
                tool_call_count=parser.result.tool_call_count,
                exit_code=proc.returncode or 0,
                stderr_output=stderr_output,
            )
        finally:
            try:
                os.unlink(prompt_file)
            except OSError:
                pass

    def _build_command(self, prompt_file: str) -> list[str]:
        cmd = [
            "gemini",
            "--prompt", f"@{prompt_file}",
            "--output-format", "stream-json",
            "--model", self._model,
            "--yolo",
        ]
        if self._mcp_server_path:
            cmd += ["--mcp-server", self._mcp_server_path]
        return cmd

    async def _read_stdout(self, proc: asyncio.subprocess.Process, parser: NDJSONStreamParser) -> None:
        assert proc.stdout is not None
        async for line in proc.stdout:
            done = await parser.feed_line(line.decode("utf-8", errors="replace"))
            if done:
                break

    async def _read_stderr(self, proc: asyncio.subprocess.Process) -> str:
        assert proc.stderr is not None
        lines = []
        async for line in proc.stderr:
            decoded = line.decode("utf-8", errors="replace").rstrip()
            if decoded:
                logger.debug("[gemini stderr] %s", decoded)
                lines.append(decoded)
        return "\n".join(lines)
