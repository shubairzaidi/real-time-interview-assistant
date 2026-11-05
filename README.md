# Real-Time Interview Assistant POC

This repository contains the Angular and FastAPI foundation, browser microphone capture, Deepgram live speech-to-text, interview question detection, and streamed OpenRouter answer generation. It does not include conversation memory or answer modes.

## Run locally

Start the backend in one PowerShell terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Add DEEPGRAM_API_KEY and OPENROUTER_API_KEY to backend/.env before starting.
# OPENROUTER_MODEL defaults to openai/gpt-4.1-mini when unset.
uvicorn app.main:app --env-file .env --reload
```

The health check is available at `http://127.0.0.1:8000/health`.

Start the frontend in a second PowerShell terminal:

```powershell
cd frontend
npm install
npm start
```

Open `http://localhost:4200`, select **Connect**, enter text, and select **Send**. The FastAPI WebSocket echoes the text into the received-message list.

## Test microphone streaming

1. Use Chrome, Edge, or another browser that supports `MediaRecorder`.
2. Open `http://localhost:4200` and select **Connect**. Wait for the connection status to become `Connected`.
3. Select **Start Listening** and allow microphone access when the browser asks.
4. Speak for a few seconds, then select **Stop Listening**.
5. Check the backend terminal for messages such as `Received audio chunk: 1234 bytes`.

If access is denied, the page displays `Microphone permission: Denied`. Stopping the recording, disconnecting, or leaving the page stops every microphone track and releases the browser resource.

## Test live transcription

1. Put a valid Deepgram key in `backend/.env` as `DEEPGRAM_API_KEY=...`. Do not put the key in the frontend.
2. Start both applications using the commands above and open `http://localhost:4200`.
3. Select **Connect**. The live transcription panel should say `Deepgram is ready.`
4. Select **Start Listening**, allow microphone access, and speak a short sentence.
5. Confirm that temporary words appear under **Interim transcript**, then confirmed words move to **Final transcript**.

The page displays the actual `MediaRecorder` MIME type. The backend logs it but leaves Deepgram's `encoding` and `sample_rate` unset so the streamed WebM/Opus container can be detected automatically.

## Test question detection

Question detection waits for Deepgram's `speech_final` event, so it uses only confirmed transcript segments from one completed utterance. It then checks whether the utterance starts with a common interview pattern.

| Spoken utterance | Expected result |
| --- | --- |
| `What is dependency injection?` | Detected question |
| `Explain Python decorators.` | Detected question |
| `Tell me about a challenging project.` | Detected question |
| `Can you explain the difference between a list and a tuple?` | Detected question |
| `How are you implementing authentication?` | Detected question |
| `Walk me through your project architecture.` | Detected question |
| `Hello, thank you for joining.` | Ignored |
| `How are you today?` | Ignored as small talk |
| `Okay, let us begin.` | Ignored |

With Deepgram and the microphone running, speak one of the question examples and pause briefly. Its text appears in **Detected Question** after Deepgram finalizes the utterance. A later detected question replaces the previous value.

## Test streamed answer generation

1. Add a valid `OPENROUTER_API_KEY` to `backend/.env`. Keep this file local; it is ignored by Git.
2. Optionally set `OPENROUTER_MODEL=openai/gpt-4.1-mini`. This is the backend default when no model value is set.
3. Start both applications and connect the browser WebSocket.
4. Paste relevant resume details and the job description into the two **Interview Context** textareas.
5. Start listening, ask a supported interview question, then pause for Deepgram to finalize it.
6. Confirm that **Detected Question** updates first and **Suggested Answer** receives text progressively.

Each textarea and the backend limit context to 6,000 characters. Context is stored only for the active WebSocket session and is never written to disk or logged.

## File responsibilities

- `.env.example` — example local environment values reserved for later configuration.
- `.gitignore` — prevents local dependencies, build output, environment values, and editor files from being committed.
- `backend/requirements.txt` — Python packages needed to run the API.
- `backend/app/__init__.py` — marks the API directory as a Python package.
- `backend/app/main.py` — FastAPI application, health endpoint, and echo WebSocket endpoint.
- `frontend/package.json` and `frontend/package-lock.json` — frontend scripts and reproducible npm dependency versions.
- `frontend/angular.json` — Angular build and development-server configuration.
- `frontend/tsconfig.json` and `frontend/tsconfig.app.json` — TypeScript compiler configuration.
- `frontend/.editorconfig` and `frontend/.gitignore` — frontend formatting and ignored local files.
- `frontend/src/index.html` — HTML page that hosts the Angular application.
- `frontend/src/main.ts` — Angular application bootstrap entry point.
- `frontend/src/styles.css` — global styles (currently intentionally empty).
- `frontend/src/app/app.config.ts` — application-wide Angular providers.
- `frontend/src/app/app.component.ts` — page behavior and button handlers.
- `frontend/src/app/app.component.html` — the minimal connection and messaging interface.
- `frontend/src/app/app.component.css` — simple layout styles for the interface.
- `frontend/src/app/websocket.service.ts` — browser WebSocket connection, status, sending, and received-message state.
