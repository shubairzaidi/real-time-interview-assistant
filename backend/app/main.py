import asyncio
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.openrouter_client import (
    OpenRouterStreamError,
    build_answer_messages,
    stream_answer_tokens,
)
from app.question_detector import detect_interview_question


logger = logging.getLogger("uvicorn.error")

# Resolve the .env file from this backend directory, not the Uvicorn working directory.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


app = FastAPI(title="Real-Time Interview Assistant API")

MAX_CONTEXT_CHARS = 6000
OPENROUTER_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def deepgram_url() -> str:
    """Build a live transcription URL for browser-provided container audio."""
    options = {
        "model": "nova-3",
        "interim_results": "true",
        "punctuate": "true",
        "endpointing": "300",
    }
    # MediaRecorder sends a browser container such as WebM/Opus, not raw PCM.
    # Do not add encoding or sample_rate; Deepgram detects the container format.
    return f"wss://api.deepgram.com/v1/listen?{urlencode(options)}"


async def send_deepgram_status(websocket: WebSocket, status: str, message: str) -> None:
    """Send a small status update that the Angular client can display."""
    await websocket.send_json(
        {"type": "deepgram_status", "status": status, "message": message}
    )


async def send_audio_chunk(audio_chunk, deepgram_socket, reconnect_deepgram):
    """Send audio and reconnect once when Deepgram closed during an idle period."""
    try:
        await deepgram_socket.send(audio_chunk)
        return deepgram_socket
    except ConnectionClosed:
        logger.warning("Deepgram closed while audio was streaming. Reconnecting.")

    replacement_socket = await reconnect_deepgram()
    if replacement_socket is None:
        return None

    try:
        await replacement_socket.send(audio_chunk)
        return replacement_socket
    except ConnectionClosed:
        logger.warning("Deepgram closed again before the audio chunk could be retried.")
        await replacement_socket.close()
        return None


def limit_context(value: object) -> str:
    """Keep browser-provided context within a predictable request size."""
    if not isinstance(value, str):
        return ""

    return value[:MAX_CONTEXT_CHARS]


async def send_answer_error(websocket: WebSocket, message: str) -> None:
    """Send a safe answer error unless the browser WebSocket is already closed."""
    try:
        await websocket.send_json({"type": "answer_error", "message": message})
    except (WebSocketDisconnect, RuntimeError):
        pass


async def stream_answer_to_browser(
    websocket: WebSocket,
    question: str,
    resume: str,
    job_description: str,
) -> None:
    """Request an answer from OpenRouter and relay its text tokens to Angular."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")

    if not api_key:
        await send_answer_error(
            websocket,
            "Answer generation is unavailable because OPENROUTER_API_KEY is not configured.",
        )
        return

    try:
        await websocket.send_json({"type": "answer_start", "question": question})
        messages = build_answer_messages(question, resume, job_description)

        async with httpx.AsyncClient(timeout=OPENROUTER_TIMEOUT) as client:
            async for token in stream_answer_tokens(client, api_key, model, messages):
                await websocket.send_json({"type": "answer_delta", "delta": token})

        await websocket.send_json({"type": "answer_complete"})
    except asyncio.CancelledError:
        raise
    except httpx.TimeoutException:
        logger.warning("OpenRouter answer request timed out.")
        await send_answer_error(websocket, "Answer generation timed out. Please try again.")
    except httpx.HTTPStatusError as error:
        logger.warning("OpenRouter returned HTTP status %s.", error.response.status_code)
        await send_answer_error(websocket, "Answer generation is unavailable. Please try again.")
    except (httpx.RequestError, OpenRouterStreamError):
        logger.warning("OpenRouter answer stream failed.")
        await send_answer_error(websocket, "Answer generation was interrupted. Please try again.")
    except (WebSocketDisconnect, RuntimeError):
        pass


async def forward_transcripts(
    deepgram_socket, browser_socket: WebSocket, on_question_detected
) -> None:
    """Forward Deepgram results to the browser as structured JSON messages."""
    final_segments: list[str] = []

    try:
        async for event in deepgram_socket:
            if not isinstance(event, str):
                continue

            response = json.loads(event)
            if response.get("type") != "Results":
                continue

            alternatives = response.get("channel", {}).get("alternatives", [])
            transcript = alternatives[0].get("transcript", "") if alternatives else ""
            is_final = response.get("is_final", False)
            speech_final = response.get("speech_final", False)

            if transcript:
                await browser_socket.send_json(
                    {
                        "type": "transcript",
                        "transcript": transcript,
                        "is_final": is_final,
                        "speech_final": speech_final,
                    }
                )

            if is_final and transcript:
                final_segments.append(transcript)

                if len(" ".join(final_segments)) > 4000:
                    logger.warning("Resetting an unusually long transcript buffer.")
                    final_segments.clear()

            if speech_final:
                utterance = " ".join(final_segments)
                final_segments.clear()
                question = detect_interview_question(utterance)

                if question:
                    await browser_socket.send_json(
                        {"type": "detected_question", "question": question}
                    )
                    await on_question_detected(question)
    except ConnectionClosed:
        logger.warning("Deepgram closed the transcription connection.")
    except json.JSONDecodeError:
        logger.warning("Deepgram sent an unreadable transcription message.")
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Deepgram transcription listener stopped unexpectedly.")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Return a simple response that confirms the API is running."""
    return {"status": "ok"}


@app.websocket("/ws/interview")
async def interview_websocket(websocket: WebSocket) -> None:
    """Echo text, forward audio to Deepgram, and return transcription updates."""
    await websocket.accept()
    deepgram_socket = None
    transcript_task = None
    answer_task = None
    resume_context = ""
    job_description_context = ""

    api_key = os.getenv("DEEPGRAM_API_KEY")

    async def stop_deepgram_connection() -> None:
        """Stop the active Deepgram listener and close its socket."""
        nonlocal deepgram_socket, transcript_task

        if transcript_task is not None:
            transcript_task.cancel()
            await asyncio.gather(transcript_task, return_exceptions=True)
            transcript_task = None

        if deepgram_socket is not None:
            try:
                await deepgram_socket.close()
            except ConnectionClosed:
                pass
            deepgram_socket = None

    async def connect_to_deepgram(reconnecting: bool = False) -> bool:
        """Open one Deepgram socket and one matching transcript listener task."""
        nonlocal deepgram_socket, transcript_task

        if not api_key:
            return False

        if reconnecting:
            await send_deepgram_status(
                websocket, "reconnecting", "Deepgram reconnecting…"
            )

        await stop_deepgram_connection()

        try:
            deepgram_socket = await connect(
                deepgram_url(),
                additional_headers={"Authorization": f"Token {api_key}"},
            )
            transcript_task = asyncio.create_task(
                forward_transcripts(
                    deepgram_socket, websocket, start_answer_generation
                )
            )
            message = "Deepgram reconnected and ready." if reconnecting else "Deepgram is ready."
            await send_deepgram_status(websocket, "connected", message)
            return True
        except Exception:
            logger.exception("Unable to connect to Deepgram.")
            await send_deepgram_status(
                websocket,
                "error",
                "Unable to connect to Deepgram. Check the API key and backend logs.",
            )
            return False

    async def start_answer_generation(question: str) -> None:
        """Cancel an older answer before starting one for the latest question."""
        nonlocal answer_task

        if answer_task is not None and not answer_task.done():
            answer_task.cancel()
            await asyncio.gather(answer_task, return_exceptions=True)

        answer_task = asyncio.create_task(
            stream_answer_to_browser(
                websocket, question, resume_context, job_description_context
            )
        )

    try:
        if not api_key:
            await send_deepgram_status(
                websocket,
                "error",
                "Deepgram is unavailable because DEEPGRAM_API_KEY is not configured.",
            )
        else:
            await connect_to_deepgram()

        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            text = message.get("text")
            audio_chunk = message.get("bytes")

            if text is not None:
                try:
                    control_message = json.loads(text)
                except json.JSONDecodeError:
                    await websocket.send_text(text)
                else:
                    if (
                        isinstance(control_message, dict)
                        and control_message.get("type") == "audio_format"
                    ):
                        logger.info(
                            "Browser MediaRecorder MIME type: %s",
                            control_message.get("mime_type", "unknown"),
                        )
                    elif (
                        isinstance(control_message, dict)
                        and control_message.get("type") == "interview_context"
                    ):
                        resume_context = limit_context(control_message.get("resume"))
                        job_description_context = limit_context(
                            control_message.get("job_description")
                        )
                    else:
                        await websocket.send_text(text)
            elif audio_chunk is not None:
                logger.info("Received audio chunk: %s bytes", len(audio_chunk))
                if deepgram_socket is not None:
                    async def reconnect_deepgram():
                        if await connect_to_deepgram(reconnecting=True):
                            return deepgram_socket
                        return None

                    deepgram_socket = await send_audio_chunk(
                        audio_chunk, deepgram_socket, reconnect_deepgram
                    )
    except WebSocketDisconnect:
        pass
    finally:
        if answer_task is not None:
            answer_task.cancel()
            await asyncio.gather(answer_task, return_exceptions=True)

        await stop_deepgram_connection()
