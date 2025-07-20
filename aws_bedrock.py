# model_id=anthropic.claude-3-7-sonnet-20250219-v1:0

import boto3
from botocore.exceptions import ClientError
import json
import logging

# Create a Bedrock Runtime client in the AWS Region you want to use.
client = boto3.client("bedrock-runtime", region_name="us-east-1")

# Set the model ID and inference profile ARN for Claude 3.7 Sonnet
model_id = "anthropic.claude-3-7-sonnet-20250219-v1:0"
inference_profile_arn = "arn:aws:bedrock:us-east-1:058264125602:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0"

# Example function to invoke Claude 3.7 Sonnet using the inference profile ARN

# def invoke_claude(messages, max_tokens=512, temperature=0.5, system=None):
#     """
#     Invoke Claude 3.7 Sonnet via Bedrock. Each message's content must be a list of dicts with a 'type' field (e.g., {'type': 'text', 'text': ...}).
#     Args:
#         messages: List of dicts with 'role' ('user' or 'assistant') and 'content' (list of {'type': 'text', 'text': ...}).
#         max_tokens: Output token limit.
#         temperature: Sampling temperature.
#         top_p: Nucleus sampling.
#         system: (Optional) System prompt string.
#     Returns:
#         Model response dict.
#     """
#     request_body = {
#         "messages": messages,
#         "max_tokens": max_tokens,
#         "temperature": temperature,
#         "anthropic_version": "bedrock-2023-05-31"
#     }
#     if system:
#         request_body["system"] = system
#     try:
#         logging.debug(f"Bedrock request body: {request_body}")
#         response = client.invoke_model(
#             modelId=inference_profile_arn,
#             body=json.dumps(request_body).encode("utf-8")
#         )
#         raw_body = response["body"].read().decode()
#         logging.debug(f"Bedrock raw response: {raw_body}")
#         return raw_body
#     except Exception as e:
#         logging.error(f"Error invoking Bedrock model: {e}")
#         raise


def converse_with_claude_stream(messages, max_tokens=2048, temperature=0.5, top_p=0.9):
    """
    Sends a conversation to Claude 3.7 Sonnet via Bedrock's streaming API and returns the full response as a string.
    Args:
        messages (list): List of messages in Anthropic format.
        max_tokens (int): Max tokens for the response.
        temperature (float): Sampling temperature.
        top_p (float): Nucleus sampling parameter.
    Returns:
        str: The full streamed response from Claude.
    """
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    inference_profile_arn = "arn:aws:bedrock:us-east-1:058264125602:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    try:
        streaming_response = client.converse_stream(
            modelId=inference_profile_arn,
            messages=messages,
            inferenceConfig={
                "maxTokens": max_tokens,
                "temperature": temperature,
                "topP": top_p
            },
        )
        full_response = ""
        for chunk in streaming_response["stream"]:
            if "contentBlockDelta" in chunk:
                text = chunk["contentBlockDelta"]["delta"]["text"]
                full_response += text
        return full_response
    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke Claude. Reason: {e}")
        return None


