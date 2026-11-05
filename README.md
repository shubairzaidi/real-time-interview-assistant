# Real-Time Interview Assistant POC

A real-time interview assistant built with **Angular, FastAPI, Deepgram and OpenRouter**. It captures interviewer audio through the browser microphone, converts speech into text, detects interview questions and streams AI-generated suggested answers.

## Features

- Browser microphone capture using `MediaRecorder`.
- Binary audio streaming from Angular to FastAPI over WebSocket.
- Live speech-to-text using Deepgram Nova-3.
- Separate interim and final transcript display.
- Rule-based interview question detection using confirmed speech segments.
- Streaming answer generation using OpenRouter LLM APIs.
- Resume and job description context for personalized answers.
- Previous answer cleared when a new question is detected.
- Basic WebSocket error handling and Deepgram reconnection attempts.
- Responsive dashboard with listening, thinking and answering status.

## Architecture

```text
Browser Microphone
       |
       v
Angular + MediaRecorder
       |
       | Audio chunks (WebSocket)
       v
FastAPI Backend
       |
       v
Deepgram Streaming STT
       |
       | Interim / Final Transcript
       v
Question Detection
       |
       | Detected Question
       v
OpenRouter LLM
       |
       | Streaming Answer Tokens
       v
Angular Dashboard
       |
       v
Suggested Answer
```

Resume and job description are sent separately as interview context and used when generating answers.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Angular, TypeScript |
| Backend | Python, FastAPI |
| Communication | WebSockets |
| Speech-to-Text | Deepgram Nova-3 |
| LLM | OpenRouter |
| HTTP Client | HTTPX |

## Prerequisites

- Python 3.10+
- Node.js and npm
- Deepgram API key
- OpenRouter API key
- Chrome or Edge browser with microphone access

## Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/shubairzaidi/real-time-interview-assistant.git
cd real-time-interview-assistant
```

### 2. Configure the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Add your API keys to `backend/.env`:

```env
DEEPGRAM_API_KEY=your_deepgram_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=openai/gpt-4.1-mini
```

Never commit your `.env` file or expose API keys in the frontend.

Start the backend:

```powershell
uvicorn app.main:app --env-file .env --reload
```

Backend health check:

`http://127.0.0.1:8000/health`

### 3. Start the frontend

Open another terminal:

```powershell
cd frontend
npm install
npm start
```

Open `http://localhost:4200` in your browser.

## How to Use

1. Start both backend and frontend applications.
2. Open the Angular application.
3. Enter your resume details and job description in the Interview Context fields.
4. Select **Connect** to establish the backend WebSocket connection.
5. Select **Start Listening** and allow microphone access.
6. Ask an interview question through the microphone.
7. Watch the interim and final transcripts update.
8. Once Deepgram finalizes the utterance, the question detector checks whether it is an interview question.
9. The detected question is sent to the LLM along with the interview context.
10. The suggested answer streams progressively into the dashboard.
11. Select **Stop Listening** when finished.

## Question Detection

Question detection uses a rule-based approach.

It checks confirmed transcript segments after Deepgram emits the `speech_final` event.

Supported patterns include:

- WH questions: What, Why, How, When, Where, Which and Who.
- Auxiliary and modal openings: Can, Could, Would, Will, Is, Are, Do and Have.
- Interview instructions: Explain, Describe, Discuss and Compare.
- Common interview phrases: Tell me about and Walk me through.

Greetings, acknowledgements and common small-talk phrases are ignored.

This is a lightweight heuristic approach and may not detect every indirectly phrased interview question.

## Answer Generation

The backend sends the detected question, resume context and job description to OpenRouter.

The LLM prompt is designed to:

- Generate concise, natural, spoken answers.
- Prefer approximately 60–90 words.
- Use 3–5 bullets when appropriate.
- Avoid inventing experience, tools or project details.
- Acknowledge missing information instead of making unsupported claims.

Answers are streamed token by token to the Angular dashboard.

## Tests

Backend unit tests:

```powershell
cd backend
pytest
```

The tests cover question detection and OpenRouter answer-generation logic.

## Project Structure

```text
real-time-interview-assistant/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── openrouter_client.py
│   │   └── question_detector.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_openrouter_client.py
│   │   └── test_question_detector.py
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── app.component.ts
│   │   │   ├── app.component.html
│   │   │   ├── app.component.css
│   │   │   ├── app.config.ts
│   │   │   └── websocket.service.ts
│   │   ├── styles.css
│   │   ├── index.html
│   │   └── main.ts
│   ├── angular.json
│   ├── package.json
│   └── tsconfig.json
│
├── .env.example
├── .gitignore
└── README.md
```

### Important File Responsibilities

| File | Responsibility |
|---|---|
| `main.py` | FastAPI application, WebSocket communication, Deepgram connection, transcript handling and answer streaming orchestration. |
| `question_detector.py` | Rule-based interview question detection. |
| `openrouter_client.py` | LLM prompt construction and OpenRouter streaming response handling. |
| `websocket.service.ts` | Angular WebSocket connection, audio transmission and backend event handling. |
| `app.component.ts` | Microphone lifecycle, interview context and dashboard behavior. |
| `app.component.html` | Dashboard layout and UI elements. |
| `app.component.css` | Dashboard component styling. |
| `styles.css` | Global application styles. |

## Current Limitations

- Question detection is heuristic-based and may miss indirect questions.
- Browser microphone audio capture is supported; system/tab audio capture is not implemented.
- Conversation memory and multiple answer modes are not implemented.
- No persistent database or user authentication.
- Reconnection is best-effort and has not been validated for every failure scenario.
- Performance depends on network conditions and external STT/LLM API response times.

## Future Improvements

- Improve question detection using an LLM-based classifier.
- Add conversation memory for follow-up questions.
- Introduce answer modes such as concise, detailed and technical.
- Add latency monitoring and performance optimization.
- Improve reconnection and session recovery.
- Add automated integration tests and deployment support.
