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
        body = {"instance_id": instance_id}
        try:
            return self._request("POST", f"{self.api_base_url}/models/unload", json=body)
        except LMStudioClientError as exc:
            message = str(exc).lower()
            # Current LM Studio expects instance_id; do not fallback if it is required.
            if (
                "missing required field 'instance_id'" in message
                or "missing_required_parameter" in message
                or "unrecognized key" in message
            ):
                raise
            if not model_id_fallback:
                raise
            return self._request(
                "POST",
                f"{self.api_base_url}/models/unload",
                json={"model": model_id_fallback, "identifier": model_id_fallback},
            )

    def unload_all_loaded_models(self) -> list[dict[str, Any]]:
        unloaded: list[dict[str, Any]] = []
        models = self.list_models()
        for model in models:
            loaded_instances = model.get("loaded_instances")
            if not isinstance(loaded_instances, list):
                continue
            for instance in loaded_instances:
                if isinstance(instance, dict):
                    instance_id = (
                        instance.get("id")
                        or instance.get("instance_id")
                        or instance.get("identifier")
                    )
                else:
                    instance_id = instance
                if not instance_id:
                    continue
                try:
                    response = self.unload_model(
                        instance_id=str(instance_id),
                        model_id_fallback=model.get("selected_variant") or model.get("key"),
                    )
                    unloaded.append(
                        {
                            "instance_id": str(instance_id),
                            "model_hint": model.get("selected_variant") or model.get("key"),
                            "response": response,
                        }
                    )
                except LMStudioClientError:
                    # Keep this best-effort: cleanup should not block full run.
                    continue
        return unloaded

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

    def chat_rest(
        self,
        *,
        model_id: str,
        system_prompt: str = "",
        input_items: list[dict[str, Any]],
        temperature: float,
        top_p: float,
        max_output_tokens: int,
        reasoning: str = "default",
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model_id,
            "input": [dict(item) for item in input_items],
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        if system_prompt.strip():
            body["system_prompt"] = system_prompt.strip()
        if reasoning in {"on", "off"}:
            body["reasoning"] = reasoning
        return self._request("POST", f"{self.api_base_url}/chat", json=body)


def build_rest_input_items(system_prompt: str, user_prompt: str, image_data_url: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if user_prompt.strip():
        items.append({"type": "text", "content": user_prompt.strip()})
    items.append({"type": "image", "data_url": image_data_url})
    return items


def normalize_rest_chat_response(
    payload: dict[str, Any],
    *,
    reasoning_requested: str,
    max_output_tokens: int | None,
) -> dict[str, Any]:
    output = payload.get("output") if isinstance(payload, dict) else None
    if not isinstance(output, list):
        final_content = ""
        reasoning_content = ""
        output_source = "bad_rest_response"
        no_final_answer = True
        bad_rest_response = True
        normalization_error_type: str | None = "bad_rest_response"
    else:
        reasoning_parts: list[str] = []
        final_content = ""
        message_seen = False
        for item in output:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            content = item.get("content")
            if item_type == "reasoning" and content is not None:
                reasoning_parts.append(str(content))
            if item_type == "message":
                message_seen = True
                text = "" if content is None else str(content)
                if not final_content and text.strip():
                    final_content = text

        reasoning_content = "\n".join(reasoning_parts)
        bad_rest_response = False
        if not output:
            output_source = "empty"
            no_final_answer = True
            normalization_error_type = "empty_rest_output"
        elif message_seen:
            output_source = "message"
            no_final_answer = not bool(final_content.strip())
            normalization_error_type = "no_final_answer" if no_final_answer else None
        else:
            output_source = "empty"
            no_final_answer = True
            normalization_error_type = "no_final_answer"

    stats = payload.get("stats") if isinstance(payload, dict) else None
    prompt_tokens = stats.get("input_tokens") if isinstance(stats, dict) else None
    completion_tokens = stats.get("total_output_tokens") if isinstance(stats, dict) else None
    reasoning_tokens = stats.get("reasoning_output_tokens") if isinstance(stats, dict) else None
    tokens_per_second = stats.get("tokens_per_second") if isinstance(stats, dict) else None
    time_to_first_token_seconds = stats.get("time_to_first_token_seconds") if isinstance(stats, dict) else None
    total_tokens = None
    if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
        total_tokens = prompt_tokens + completion_tokens

    finish_reason = payload.get("finish_reason") if isinstance(payload, dict) else None
    output_truncated = False
    if isinstance(finish_reason, str):
        output_truncated = finish_reason == "length"
    elif isinstance(completion_tokens, int) and isinstance(max_output_tokens, int):
        output_truncated = completion_tokens >= max_output_tokens

    final_content_empty = not bool(final_content.strip())
    result = {
        "transport": "rest",
        "reasoning_requested": reasoning_requested,
        "final_content": final_content,
        "reasoning_content": reasoning_content,
        "output_source": output_source,
        "final_content_empty": final_content_empty,
        "reasoning_content_present": bool(reasoning_content.strip()),
        "final_content_length": len(final_content),
        "reasoning_content_length": len(reasoning_content),
        "no_final_answer": no_final_answer,
        "bad_rest_response": bad_rest_response,
        "normalization_error_type": normalization_error_type,
        "finish_reason": finish_reason,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "reasoning_tokens": reasoning_tokens,
        "tokens_per_second": tokens_per_second,
        "time_to_first_token_seconds": time_to_first_token_seconds,
        "output_truncated": output_truncated,
        "raw_response": payload,
        "raw_output": final_content,
        "content_empty": final_content_empty,
        "content_length": len(final_content),
        "reasoning_content_used": False,
    }
    return result
