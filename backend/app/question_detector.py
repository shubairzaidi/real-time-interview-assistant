"""Simple rule-based detection for completed interview utterances."""

import re


WH_QUESTION_WORDS = {"what", "why", "how", "when", "where", "which", "who"}
AUXILIARY_QUESTION_WORDS = {
    "do",
    "does",
    "did",
    "is",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "can",
    "could",
    "would",
    "will",
    "should",
}
INSTRUCTION_VERBS = {"explain", "describe", "discuss", "compare", "outline"}
ACKNOWLEDGEMENTS = {"okay", "ok", "thanks", "thank you", "sounds good", "great"}
LEADING_FILLERS = {"okay", "ok", "alright", "so"}


def normalize(utterance: str) -> str:
    """Lowercase and remove punctuation so word matching is consistent."""
    without_punctuation = re.sub(r"[^a-z0-9\s]", " ", utterance.lower())
    return " ".join(without_punctuation.split())


def is_small_talk(words: list[str], normalized: str) -> bool:
    """Ignore short greetings and acknowledgements, not technical questions."""
    if normalized in ACKNOWLEDGEMENTS:
        return True

    if normalized in {"how are you", "how are you doing", "how are you today"}:
        return True

    if len(words) == 5 and words[:2] in (
        ["good", "morning"],
        ["good", "afternoon"],
        ["good", "evening"],
    ) and words[2:] == ["how", "are", "you"]:
        return True

    return False


def remove_leading_greeting_or_filler(words: list[str]) -> list[str]:
    """Allow a question after a brief greeting such as 'Okay, can you...'"""
    if words[:2] in (
        ["good", "morning"],
        ["good", "afternoon"],
        ["good", "evening"],
    ):
        return words[2:]

    if words and words[0] in {"hello", "hi", "hey", *LEADING_FILLERS}:
        return words[1:]

    return words


def detect_interview_question(utterance: str) -> str | None:
    """Return a completed utterance when it has a common question structure."""
    question = " ".join(utterance.split()).strip()
    normalized = normalize(question)
    words = normalized.split()

    if not words or is_small_talk(words, normalized):
        return None

    words = remove_leading_greeting_or_filler(words)
    if not words:
        return None

    first_word = words[0]

    if first_word in WH_QUESTION_WORDS or first_word in AUXILIARY_QUESTION_WORDS:
        return question

    if first_word in INSTRUCTION_VERBS:
        return question

    if words[:3] in (["tell", "me", "about"], ["tell", "us", "about"]):
        return question

    if len(words) >= 3 and words[0] == "walk" and words[1] in {"me", "us"} and words[2] == "through":
        return question

    if words[:2] == ["difference", "between"]:
        return question

    return None
