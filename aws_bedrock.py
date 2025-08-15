
import os
import boto3
from botocore.exceptions import ClientError
import json
import logging
import re
import time
from functools import lru_cache
from dotenv import load_dotenv
load_dotenv()
# Centralized Bedrock Runtime client and configuration via environment variables
# AWS_REGION (default us-east-1)
# Claude: ONLY AWS_CLAUDE_INFERENCE_PROFILE_ARN (Inference Profile ARN)
# Titan (embeddings): ONLY AWS_TITAN_MODEL_ID (handled in vector_utils)
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return _client

INFERENCE_PROFILE_ARN = os.getenv("AWS_CLAUDE_INFERENCE_PROFILE_ARN")


def _is_bedrock_configured() -> bool:
    # Require inference profile ARN explicitly for Claude usage
    return bool(INFERENCE_PROFILE_ARN)



# Simple response cache for non-streaming calls
_RESP_CACHE: dict = {}
_CACHE_TTL_SECONDS = int(os.getenv("BEDROCK_CACHE_TTL", "120"))


def _cache_get(key: str):
    try:
        ts, val = _RESP_CACHE.get(key, (0, None))
        if time.time() - ts <= _CACHE_TTL_SECONDS:
            return val
    except Exception:
        pass
    return None


def _cache_set(key: str, val: str):
    try:
        _RESP_CACHE[key] = (time.time(), val)
    except Exception:
        pass


@lru_cache(maxsize=64)
def _model_id() -> str:
    if not INFERENCE_PROFILE_ARN:
        raise RuntimeError("AWS_CLAUDE_INFERENCE_PROFILE_ARN is not set")
    return INFERENCE_PROFILE_ARN

def converse_with_claude_stream(messages, max_tokens=512, temperature=0.5, top_p=0.9):
    """
    Sends a conversation to Claude 4 Sonnet via Bedrock's streaming API and yields tokens as they arrive.
    Args:
        messages (list): List of messages in Anthropic format.
        max_tokens (int): Max tokens for the response.
        temperature (float): Sampling temperature.
        top_p (float): Nucleus sampling parameter.
    Yields:
        str: Next token from the streamed response.
    """
    try:
        if not _is_bedrock_configured():
            raise RuntimeError("Bedrock not configured: set AWS_CLAUDE_INFERENCE_PROFILE_ARN")
        retries = 2
        last_exc = None
        for attempt in range(retries + 1):
            try:
                streaming_response = _get_client().converse_stream(
                    modelId=_model_id(),
                    messages=messages,
                    inferenceConfig={
                        "maxTokens": max_tokens,
                        "temperature": temperature,
                        "topP": top_p
                    },
                )
                for chunk in streaming_response["stream"]:
                    if "contentBlockDelta" in chunk:
                        text = chunk["contentBlockDelta"]["delta"].get("text") or ""
                        if text:
                            yield text
                    # Handle message stop gracefully to ensure callers don't hang
                    if "messageStop" in chunk:
                        break
                return
            except Exception as ie:
                last_exc = ie
                time.sleep(0.25 * (attempt + 1))
        raise last_exc
    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke Claude. Reason: {e}")
        err = f"Configuration/Invocation error: {e}"
        for i in range(0, len(err), 50):
            yield err[i:i+50]

def converse_with_claude(messages, max_tokens=512, temperature=0.5, top_p=0.9):
    """
    Sends a conversation to Claude 4 Sonnet via Bedrock's non-streaming API and returns the complete response.
    Args:
        messages (list): List of messages in Anthropic format.
        max_tokens (int): Max tokens for the response.
        temperature (float): Sampling temperature.
        top_p (float): Nucleus sampling parameter.
    Returns:
        str: Complete response from Claude.
    """
    try:
        # Build cache key (includes model ARN)
        try:
            key = json.dumps({"m": messages, "t": max_tokens, "temp": temperature, "p": top_p, "model": _model_id()}, sort_keys=True)
        except Exception:
            key = str(messages)[:1000]

        cached = _cache_get(key)
        if cached is not None:
            return cached

        if not _is_bedrock_configured():
            raise RuntimeError("Bedrock not configured: set AWS_CLAUDE_INFERENCE_PROFILE_ARN")

        retries = 2
        last_exc = None
        response = None
        for attempt in range(retries + 1):
            try:
                response = _get_client().converse(
                    modelId=_model_id(),
                    messages=messages,
                    inferenceConfig={
                        "maxTokens": max_tokens,
                        "temperature": temperature,
                        "topP": top_p
                    },
                )
                break
            except Exception as ie:
                last_exc = ie
                time.sleep(0.25 * (attempt + 1))
        if response is None:
            raise last_exc
        # Normalize different possible response formats from Bedrock
        try:
            # anthropic converse returns {"output": {"message": {"content":[{"text": ...}]}} in newer SDKs
            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            if content and isinstance(content, list):
                first = content[0]
                if isinstance(first, dict) and "text" in first:
                    text = first["text"]
                    _cache_set(key, text)
                    return text
            # backwards compatibility
            if "content" in response and response["content"]:
                first = response["content"][0]
                if isinstance(first, dict) and "text" in first:
                    text = first["text"]
                    _cache_set(key, text)
                    return text
                if isinstance(first, str):
                    _cache_set(key, first)
                    return first
            if "response" in response:
                _cache_set(key, response["response"])
                return response["response"]
            text = json.dumps(response)
            _cache_set(key, text)
            return text
        except Exception:
            text = json.dumps(response)
            _cache_set(key, text)
            return text
    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke Claude. Reason: {e}")
        return f"Configuration/Invocation error: {e}"


