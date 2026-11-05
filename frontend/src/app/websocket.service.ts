import { Injectable } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

type ConnectionStatus = 'Disconnected' | 'Connecting' | 'Connected';

type TranscriptEvent = {
  type?: string;
  transcript?: string;
  is_final?: boolean;
  speech_final?: boolean;
  question?: string;
  delta?: string;
  status?: string;
  message?: string;
};

@Injectable({ providedIn: 'root' })
export class WebSocketService {
  private socket?: WebSocket;
  private readonly statusSubject = new BehaviorSubject<ConnectionStatus>('Disconnected');
  private readonly messagesSubject = new BehaviorSubject<string[]>([]);
  private readonly interimTranscriptSubject = new BehaviorSubject('');
  private readonly finalTranscriptSubject = new BehaviorSubject('');
  private readonly transcriptionStatusSubject = new BehaviorSubject('Not connected');
  private readonly detectedQuestionSubject = new BehaviorSubject('');
  private readonly answerSubject = new BehaviorSubject('');
  private readonly answerStatusSubject = new BehaviorSubject('Waiting for a question');

  readonly connectionStatus = this.statusSubject.asObservable();
  readonly messages = this.messagesSubject.asObservable();
  readonly interimTranscript = this.interimTranscriptSubject.asObservable();
  readonly finalTranscript = this.finalTranscriptSubject.asObservable();
  readonly transcriptionStatus = this.transcriptionStatusSubject.asObservable();
  readonly detectedQuestion = this.detectedQuestionSubject.asObservable();
  readonly answer = this.answerSubject.asObservable();
  readonly answerStatus = this.answerStatusSubject.asObservable();

  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  connect(): void {
    if (this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.statusSubject.next('Connecting');
    this.interimTranscriptSubject.next('');
    this.finalTranscriptSubject.next('');
    this.detectedQuestionSubject.next('');
    this.answerSubject.next('');
    this.answerStatusSubject.next('Waiting for a question');
    this.transcriptionStatusSubject.next('Connecting to Deepgram');
    this.socket = new WebSocket('ws://127.0.0.1:8000/ws/interview');

    this.socket.onopen = () => this.statusSubject.next('Connected');
    this.socket.onmessage = (event) => this.handleMessage(event.data);
    this.socket.onerror = () => this.statusSubject.next('Disconnected');
    this.socket.onclose = () => {
      this.statusSubject.next('Disconnected');
      this.transcriptionStatusSubject.next('Disconnected');
    };
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = undefined;
    this.statusSubject.next('Disconnected');
  }

  send(message: string): void {
    const socket = this.socket;

    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(message);
    }
  }

  sendAudio(audioChunk: Blob): boolean {
    const socket = this.socket;

    if (socket?.readyState !== WebSocket.OPEN) {
      return false;
    }

    socket.send(audioChunk);
    return true;
  }

  sendAudioFormat(mimeType: string): void {
    this.send(JSON.stringify({ type: 'audio_format', mime_type: mimeType }));
  }

  sendInterviewContext(resume: string, jobDescription: string): void {
    const maximumContextLength = 6000;

    this.send(JSON.stringify({
      type: 'interview_context',
      resume: resume.slice(0, maximumContextLength),
      job_description: jobDescription.slice(0, maximumContextLength),
    }));
  }

  private handleMessage(data: unknown): void {
    if (typeof data !== 'string') {
      return;
    }

    try {
      const event = JSON.parse(data) as TranscriptEvent;

      if (event.type === 'transcript' && typeof event.transcript === 'string') {
        if (event.is_final) {
          const previousTranscript = this.finalTranscriptSubject.value;
          this.finalTranscriptSubject.next(
            `${previousTranscript} ${event.transcript}`.trim(),
          );
          this.interimTranscriptSubject.next('');

          if (event.speech_final) {
            this.transcriptionStatusSubject.next('Deepgram: speech final');
          }
        } else {
          this.interimTranscriptSubject.next(event.transcript);
          this.transcriptionStatusSubject.next('Deepgram: listening');
        }
        return;
      }

      if (event.type === 'deepgram_status') {
        this.transcriptionStatusSubject.next(event.message ?? event.status ?? 'Deepgram update');
        return;
      }

      if (event.type === 'detected_question' && typeof event.question === 'string') {
        this.detectedQuestionSubject.next(event.question);
        return;
      }

      if (event.type === 'answer_start') {
        this.answerSubject.next('');
        this.answerStatusSubject.next('Generating answer');
        return;
      }

      if (event.type === 'answer_delta' && typeof event.delta === 'string') {
        this.answerSubject.next(`${this.answerSubject.value}${event.delta}`);
        return;
      }

      if (event.type === 'answer_complete') {
        this.answerStatusSubject.next('Answer complete');
        return;
      }

      if (event.type === 'answer_error') {
        this.answerStatusSubject.next(event.message ?? 'Answer generation failed');
        return;
      }
    } catch {
      // Plain text messages use the existing echo behavior below.
    }

    this.messagesSubject.next([...this.messagesSubject.value, data]);
  }
}
