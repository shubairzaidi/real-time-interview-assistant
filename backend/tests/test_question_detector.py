import unittest

from app.main import forward_transcripts
from app.question_detector import detect_interview_question


class QuestionDetectorTests(unittest.TestCase):
    def test_detects_common_interview_questions_and_instructions(self) -> None:
        questions = (
            "Tell me about yourself.",
            "Explain Python decorators.",
            "What is the difference between list and tuple?",
            "How are you implementing authentication?",
            "Walk me through your project architecture.",
            "Why did you choose FastAPI?",
            "When did you work with WebSockets?",
            "Where would you add validation?",
            "Which testing tools do you use?",
            "Who did you collaborate with?",
            "Do you use type hints?",
            "Have you worked with microservices?",
            "Can you share your experience with Angular?",
            "Okay, can you share your experience with Angular?",
            "Would you change this API design?",
            "Difference between a list and a tuple.",
        )

        for question in questions:
            with self.subTest(question=question):
                self.assertEqual(detect_interview_question(question), question)

    def test_ignores_greetings_and_small_talk(self) -> None:
        statements = (
            "Good morning, how are you?",
            "How are you today?",
            "Okay, let's move ahead.",
            "Thank you.",
            "I have worked with FastAPI.",
            "The project uses a WebSocket connection.",
        )

        for statement in statements:
            with self.subTest(statement=statement):
                self.assertIsNone(detect_interview_question(statement))


class TranscriptBufferTests(unittest.IsolatedAsyncioTestCase):
    async def test_processes_only_final_segments_and_resets_after_speech_final(self) -> None:
        deepgram_socket = FakeDeepgramSocket(
            [
                result("Explain Python", is_final=False, speech_final=False),
                result("Explain Python", is_final=True, speech_final=False),
                result("decorators", is_final=True, speech_final=True),
                result("Okay lets", is_final=True, speech_final=False),
                result("move ahead", is_final=True, speech_final=True),
            ]
        )
        browser_socket = FakeBrowserSocket()

        async def do_nothing(question: str) -> None:
            return None

        await forward_transcripts(deepgram_socket, browser_socket, do_nothing)

        detected_questions = [
            event for event in browser_socket.events if event["type"] == "detected_question"
        ]
        self.assertEqual(
            detected_questions,
            [{"type": "detected_question", "question": "Explain Python decorators"}],
        )


def result(transcript: str, is_final: bool, speech_final: bool) -> str:
    return (
        '{"type":"Results","channel":{"alternatives":[{"transcript":"'
        f'{transcript}'
        '"}]},"is_final":'
        f'{str(is_final).lower()}'
        ',"speech_final":'
        f'{str(speech_final).lower()}'
        "}"
    )


class FakeDeepgramSocket:
    def __init__(self, events: list[str]) -> None:
        self.events = iter(events)

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        try:
            return next(self.events)
        except StopIteration:
            raise StopAsyncIteration


class FakeBrowserSocket:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def send_json(self, event: dict[str, object]) -> None:
        self.events.append(event)
