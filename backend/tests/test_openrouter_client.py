import json
import unittest

import httpx

from app.openrouter_client import (
    OPENROUTER_URL,
    build_answer_messages,
    stream_answer_tokens,
)


class OpenRouterClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_streams_text_deltas_from_server_sent_events(self) -> None:
        request_details: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            request_details["url"] = str(request.url)
            request_details["authorization"] = request.headers["Authorization"]
            request_details["body"] = json.loads(request.content)
            stream = (
                'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":" world"}}]}\n\n'
                "data: [DONE]\n\n"
            )
            return httpx.Response(200, content=stream)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            tokens = [
                token
                async for token in stream_answer_tokens(
                    client,
                    "test-key",
                    "test-model",
                    build_answer_messages("Explain decorators", "Python developer", "Backend role"),
                )
            ]

        self.assertEqual(tokens, ["Hello", " world"])
        self.assertEqual(request_details["url"], OPENROUTER_URL)
        self.assertEqual(request_details["authorization"], "Bearer test-key")
        self.assertTrue(request_details["body"]["stream"])

    def test_prompt_includes_question_and_context(self) -> None:
        messages = build_answer_messages(
            "Tell me about yourself.", "Built APIs with Python.", "FastAPI role."
        )

        self.assertIn("Tell me about yourself.", messages[1]["content"])
        self.assertIn("Built APIs with Python.", messages[1]["content"])
        self.assertIn("FastAPI role.", messages[1]["content"])
        self.assertIn("Do not invent", messages[0]["content"])
        self.assertIn("Dockerfiles", messages[0]["content"])
        self.assertIn("not mentioned in the supplied profile", messages[0]["content"])
        self.assertIn("between 60 and 90 words", messages[0]["content"])
        self.assertIn("3 to 5 short bullet points", messages[0]["content"])
        self.assertIn("natural, simple spoken English", messages[0]["content"])
