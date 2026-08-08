"""Agent model profile metadata for V0.2 execution audit."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentModelProfile:
    """Describes the model or stub profile used by an Agent run."""

    model_id: str
    model_version: str
    alias: str
    provider: str
    runtime: str
    api_base_url: str
    is_stub: bool

    def as_payload(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "alias": self.alias,
            "provider": self.provider,
            "runtime": self.runtime,
            "api_base_url": self.api_base_url,
            "is_stub": self.is_stub,
        }


def default_model_profile(
    environ: Mapping[str, str] | None = None,
) -> AgentModelProfile:
    source = os.environ if environ is None else environ
    return AgentModelProfile(
        model_id=source.get("BRIDGEAI_AGENT_MODEL_ID", "Vontra-DeepSeek-V4-Flash-0731-MXFP4-MLX"),
        model_version=source.get("BRIDGEAI_AGENT_MODEL_VERSION", "omlx-current"),
        alias=source.get("BRIDGEAI_AGENT_MODEL_ALIAS", "omlx-vontra-deepseek-v4-flash"),
        provider=source.get("BRIDGEAI_AGENT_MODEL_PROVIDER", "omlx"),
        runtime=source.get("BRIDGEAI_AGENT_MODEL_RUNTIME", "openai-compatible"),
        api_base_url=source.get("BRIDGEAI_AGENT_API_BASE_URL", "http://127.0.0.1:18000/v1"),
        is_stub=_parse_bool(source.get("BRIDGEAI_AGENT_MODEL_IS_STUB", "false")),
    )


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
