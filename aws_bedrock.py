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

def converse_with_claude_stream(messages, max_tokens=512, temperature=0.5, top_p=0.9):
    """
    Sends a conversation to Claude 3.7 Sonnet via Bedrock's streaming API and yields tokens as they arrive.
    Args:
        messages (list): List of messages in Anthropic format.
        max_tokens (int): Max tokens for the response.
        temperature (float): Sampling temperature.
        top_p (float): Nucleus sampling parameter.
    Yields:
        str: Next token from the streamed response.
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
        for chunk in streaming_response["stream"]:
            if "contentBlockDelta" in chunk:
                text = chunk["contentBlockDelta"]["delta"]["text"]
                yield text
    except (ClientError, Exception) as e:
        print(f"ERROR: Can't invoke Claude. Reason: {e}")
        yield '[ERROR: Claude streaming failed] '


