"""Small helpers for streaming interview answers from OpenRouter."""

import json
from collections.abc import AsyncIterator

import httpx


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterStreamError(Exception):
    """Raised when OpenRouter returns an invalid streaming response."""


def build_answer_messages(
    question: str, resume: str, job_description: str
) -> list[dict[str, str]]:
    """Build a concise prompt for a truthful, interview-ready answer."""
    system_prompt = (
        "You help a software engineering candidate prepare concise live interview answers. "
        "Keep each answer between 60 and 90 words. Use 3 to 5 short bullet points "
        "when that makes the answer easier to speak. Use natural, simple spoken English. "
        "Answer the interview question directly without an unnecessary introduction or "
        "repeated conclusion. Use specific resume or project examples when they are relevant. "
        "Use only candidate experience, tools, responsibilities, and project details "
        "explicitly supported by the supplied resume or context. Do not invent skills, "
        "achievements, Dockerfiles, Docker Compose usage, production deployments, or "
        "project implementations. If a specific experience is missing, explicitly state "
        "that it is not mentioned in the supplied profile. Keep technical explanations "
        "accurate and easy to say aloud."
    )
    user_prompt = (
        f"Interview question:\n{question}\n\n"
        f"Candidate resume:\n{resume or 'Not provided.'}\n\n"
        f"Job description:\n{job_description or 'Not provided.'}\n\n"
        "Provide a clear, interview-ready answer in a few short paragraphs."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


async def stream_answer_tokens(
    client: httpx.AsyncClient,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    """Yield text tokens from OpenRouter's Server-Sent Event response."""
    request_body = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 350,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with client.stream(
        "POST", OPENROUTER_URL, headers=headers, json=request_body
    ) as response:
        response.raise_for_status()
        stream_completed = False

        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue

            data = line.removeprefix("data: ").strip()
            if data == "[DONE]":
                stream_completed = True
                break

            try:
                event = json.loads(data)
            except json.JSONDecodeError as error:
                raise OpenRouterStreamError("OpenRouter returned invalid stream data.") from error

            if "error" in event:
                raise OpenRouterStreamError("OpenRouter returned a streaming error.")

            choices = event.get("choices", [])
            delta = choices[0].get("delta", {}) if choices else {}
            content = delta.get("content")

            if isinstance(content, str) and content:
                yield content

        if not stream_completed:
            raise OpenRouterStreamError("OpenRouter ended the stream unexpectedly.")
