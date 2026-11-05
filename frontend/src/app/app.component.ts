import { AfterViewChecked, Component, ElementRef, OnDestroy, ViewChild, inject } from '@angular/core';
import { Subscription } from 'rxjs';
import { AsyncPipe, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { WebSocketService } from './websocket.service';

@Component({
  selector: 'app-root',
  imports: [AsyncPipe, FormsModule, NgIf],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements AfterViewChecked, OnDestroy {
  private readonly webSocketService = inject(WebSocketService);
  private mediaRecorder?: MediaRecorder;
  private microphoneStream?: MediaStream;
  private listeningRequested = false;
  private shouldScrollAnswer = false;
  private readonly answerSubscription: Subscription;

  @ViewChild('answerScroll') private answerScroll?: ElementRef<HTMLDivElement>;

  readonly connectionStatus = this.webSocketService.connectionStatus;
  readonly interimTranscript = this.webSocketService.interimTranscript;
  readonly finalTranscript = this.webSocketService.finalTranscript;
  readonly transcriptionStatus = this.webSocketService.transcriptionStatus;
  readonly detectedQuestion = this.webSocketService.detectedQuestion;
  readonly answer = this.webSocketService.answer;
  readonly answerStatus = this.webSocketService.answerStatus;
  resume = '';
  jobDescription = '';
  microphonePermission = 'Not requested';
  recordingStatus = 'Not recording';
  audioMimeType = 'Not recording';

  constructor() {
    this.answerSubscription = this.answer.subscribe(() => {
      this.shouldScrollAnswer = true;
    });
  }

  get isListening(): boolean {
    return ['Starting', 'Recording', 'Stopping'].includes(this.recordingStatus);
  }

  connect(): void {
    this.webSocketService.connect();
  }

  disconnect(): void {
    this.stopListening();
    this.webSocketService.disconnect();
  }

  async startListening(): Promise<void> {
    if (this.listeningRequested) {
      return;
    }

    if (!this.webSocketService.isConnected) {
      this.recordingStatus = 'Connect the WebSocket before listening';
      return;
    }

    this.updateInterviewContext();

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      this.microphonePermission = 'Unavailable';
      this.recordingStatus = 'Audio recording is not supported by this browser';
      return;
    }

    this.microphonePermission = 'Requesting';
    this.recordingStatus = 'Starting';
    this.listeningRequested = true;

    try {
      this.microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.microphonePermission = 'Granted';

      if (!this.listeningRequested) {
        this.releaseMicrophone();
        this.recordingStatus = 'Stopped';
        return;
      }

      this.mediaRecorder = new MediaRecorder(this.microphoneStream);
      this.audioMimeType = this.mediaRecorder.mimeType || 'Browser default';
      this.webSocketService.sendAudioFormat(this.audioMimeType);

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && !this.webSocketService.sendAudio(event.data)) {
          this.stopListening();
          this.recordingStatus = 'Stopped: WebSocket disconnected';
        }
      };

      this.mediaRecorder.onstart = () => {
        this.recordingStatus = 'Recording';
      };

      this.mediaRecorder.onstop = () => {
        this.releaseMicrophone();
        this.mediaRecorder = undefined;
        this.listeningRequested = false;

        if (this.recordingStatus !== 'Stopped: WebSocket disconnected') {
          this.recordingStatus = 'Stopped';
        }
      };

      this.mediaRecorder.start(250);
    } catch (error) {
      this.microphonePermission = this.wasPermissionDenied(error) ? 'Denied' : 'Unavailable';
      this.recordingStatus = 'Not recording';
      this.releaseMicrophone();
    } finally {
      if (!this.mediaRecorder) {
        this.listeningRequested = false;
      }
    }
  }

  stopListening(): void {
    this.listeningRequested = false;

    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.recordingStatus = 'Stopping';
      this.mediaRecorder.stop();
      return;
    }

    this.releaseMicrophone();
    this.mediaRecorder = undefined;
  }

  ngOnDestroy(): void {
    this.stopListening();
    this.answerSubscription.unsubscribe();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollAnswer && this.answerScroll) {
      const answerElement = this.answerScroll.nativeElement;
      answerElement.scrollTop = answerElement.scrollHeight;
      this.shouldScrollAnswer = false;
    }
  }

  updateInterviewContext(): void {
    if (this.webSocketService.isConnected) {
      this.webSocketService.sendInterviewContext(this.resume, this.jobDescription);
    }
  }

  private releaseMicrophone(): void {
    this.microphoneStream?.getTracks().forEach((track) => track.stop());
    this.microphoneStream = undefined;
  }

  private wasPermissionDenied(error: unknown): boolean {
    return error instanceof DOMException &&
      (error.name === 'NotAllowedError' || error.name === 'SecurityError');
  }
}
