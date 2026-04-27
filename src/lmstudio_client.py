from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from src.config import BenchmarkConfig, ModelConfig


class LMStudioClientError(RuntimeError):
    """LM Studio interaction error."""


class ResponseFormatUnsupportedError(LMStudioClientError):
    """Response format rejected by backend."""


@dataclass(frozen=True)
class LoadedModel:
    id: str
    base_model_id: str
    label: str
    instance_id: str
    params: str | None
    quant: str | None
    quant_bits: int | None
    requested_context_length: int | None
    actual_context_length: int | None
    load_config: dict[str, Any]


def _looks_like_response_format_error(message: str) -> bool:
    text = message.lower()
    needles = [
        "response_format",
        "unsupported",
        "json_schema",
        "json schema",
        "invalid_request_error",
    ]
    return any(item in text for item in needles)


class LMStudioClient:
    def __init__(self, *, api_base_url: str, openai_base_url: str, api_key: str, timeout_sec: int) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.openai_base_url = openai_base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    @classmethod
    def from_config(cls, cfg: BenchmarkConfig) -> "LMStudioClient":
        return cls(
            api_base_url=cfg.lmstudio.api_base_url,
            openai_base_url=cfg.lmstudio.openai_base_url,
            api_key=cfg.lmstudio.api_key,
            timeout_sec=cfg.limits.timeout_sec,
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self.session.request(method, url, timeout=self.timeout_sec, **kwargs)
        except requests.RequestException as exc:
            raise LMStudioClientError(f"Failed to connect to LM Studio ({url}): {exc}") from exc

        if response.status_code >= 400:
            body = response.text.strip()
            message = f"LM Studio HTTP {response.status_code} for {url}: {body}"
            raise LMStudioClientError(message)

        if not response.text.strip():
            return {}
        try:
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {"data": payload}
        except ValueError as exc:
            raise LMStudioClientError(f"Non-JSON response from LM Studio ({url})") from exc

    def list_models(self) -> list[dict[str, Any]]:
        payload = self._request("GET", f"{self.api_base_url}/models")
        data = payload.get("data")
        if data is None:
            data = payload.get("models")
        if data is None:
            data = payload
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        raise LMStudioClientError("Unexpected model listing payload from LM Studio")

    def load_model(self, model: ModelConfig, load_config: dict[str, Any]) -> LoadedModel:
        body = {"model": model.id, "identifier": model.id, "load_config": load_config}
        try:
            payload = self._request("POST", f"{self.api_base_url}/models/load", json=body)
        except LMStudioClientError as exc:
            message = str(exc).lower()
            # Compatibility fallback for LM Studio variants that reject nested load_config.
            if "unrecognized key" in message and ("identifier" in message or "load_config" in message):
                flat_body: dict[str, Any] = {"model": model.id}
                flat_body.update(load_config)
                try:
                    payload = self._request("POST", f"{self.api_base_url}/models/load", json=flat_body)
                except LMStudioClientError as exc2:
                    message2 = str(exc2).lower()
                    if "model_not_found" in message2 and model.base_model_id:
                        flat_base_body: dict[str, Any] = {"model": model.base_model_id}
                        flat_base_body.update(load_config)
                        payload = self._request("POST", f"{self.api_base_url}/models/load", json=flat_base_body)
                    else:
                        raise
            elif "model_not_found" in message and model.base_model_id:
                base_body = {"model": model.base_model_id}
                base_body.update(load_config)
                payload = self._request("POST", f"{self.api_base_url}/models/load", json=base_body)
            else:
                raise
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise LMStudioClientError("Unexpected load response from LM Studio")

        instance_id = (
            data.get("id")
            or data.get("instance_id")
            or data.get("model_id")
            or data.get("identifier")
            or model.id
        )
        actual_context = None
        if isinstance(data.get("load_config"), dict):
            value = data["load_config"].get("context_length")
            actual_context = value if isinstance(value, int) else None

        return LoadedModel(
            id=model.id,
            base_model_id=model.base_model_id,
            label=model.label,
            instance_id=str(instance_id),
            params=model.params,
            quant=model.quant,
            quant_bits=model.quant_bits,
            requested_context_length=load_config.get("context_length"),
            actual_context_length=actual_context,
            load_config=data.get("load_config", {}),
        )

    def unload_model(self, instance_id: str, model_id_fallback: str | None = None) -> dict[str, Any]:
        body = {"id": instance_id, "instance_id": instance_id}
        try:
            return self._request("POST", f"{self.api_base_url}/models/unload", json=body)
        except LMStudioClientError:
            if not model_id_fallback:
                raise
            return self._request(
                "POST",
                f"{self.api_base_url}/models/unload",
                json={"model": model_id_fallback, "identifier": model_id_fallback},
            )

    def chat_completion(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        temperature: float,
        top_p: float,
        max_tokens: int,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            body["response_format"] = response_format
        try:
            return self._request("POST", f"{self.openai_base_url}/chat/completions", json=body)
        except LMStudioClientError as exc:
            if response_format is not None and _looks_like_response_format_error(str(exc)):
                raise ResponseFormatUnsupportedError(str(exc)) from exc
            raise
