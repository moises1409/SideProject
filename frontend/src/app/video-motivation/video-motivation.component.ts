import { Component, ChangeDetectorRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { HttpClientModule } from '@angular/common/http';
import { of, Observable, forkJoin, interval, throwError } from 'rxjs';
import { catchError, map, switchMap, takeWhile } from 'rxjs/operators';

interface ScriptResponse {
  complete_story: string;
  scenes: Array<{
    video_prompt: string;
    sentences: string;
  }>;
}

@Component({
  selector: 'app-video-motivation',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './video-motivation.component.html',
  styleUrl: './video-motivation.component.css'
})

export class VideoMotivationComponent {
  storyTopic: string = '';
  generatedStory: string = '';
  errorMessage: string = '';
  selectedLanguage: string = '';
  isLoading: boolean = false;
  progress: number = 0;
  progressMessage: string = '';
  generatedResults: Array<[string, string]> = [];
  video_url: string = '';

  private apiUrl_local = 'http://localhost:4000';
  private apiUrl_prod =
    'https://videoai-flaskapi-f5d4cmfncnfzaxgc.eastus-01.azurewebsites.net';

  constructor(private http: HttpClient, private cdr: ChangeDetectorRef) {}

  private getApiUrl(endpoint: string): string {
    const baseUrl = this.isProduction() ? this.apiUrl_prod : this.apiUrl_local;
    return `${baseUrl}${endpoint}`;
  }

  private isProduction(): boolean {
    return window.location.hostname !== 'localhost';
  }

  // Main function with error handling
  mainFunction(): void {
    this.startLoading();
    this.updateProgress('Generating motivational script...');
    this.generateStory()
      .pipe(
        catchError((error) => {
          this.handleError('Failed to generate the motivational script. Please try again later.', error);
          return throwError(() => error); // Stop further execution
        })
      )
      .subscribe({
        next: (response) => {
          if (response) {
            console.log('The motivational story has been generated:', response.complete_story);
            this.incrementProgress(25);
            this.generatedResults = response.scenes.map(scene => [scene.video_prompt, scene.sentences]);
            console.log('Generated Results:', this.generatedResults);
            this.generateVideo();
          } else {
            this.finishLoading();
          }
        },
        error: () => this.finishLoading(),
      });
  }


  // Function to generate the video and handle errors
  private generateVideo() {
    this.updateProgress('Generating video...');
    const apiUrl = this.getApiUrl('/video_motivation/motivation_video_editor');
    const body = { scene_data: this.generatedResults };

    this.http.post<{ task_id: string }>(apiUrl, body).subscribe({
      next: (response) => {
        const taskId = response.task_id;
        this.incrementProgress(25);
        this.pollForVideoAvailability(taskId);
      },
      error: (error) => {
        console.error('Error starting video generation:', error);
        this.finishLoading()     
      }
    });
  }

  // Poll the Azure Blob URL to check if the video is available
  private pollForVideoAvailability(taskId: string): void {
    const apiUrl = this.getApiUrl(`/generic_apis/task_status/${taskId}`);
    const pollInterval = 10000;  // Poll every 10 seconds
    let retries = 0;
    const maxRetries = 60;  // Poll for a maximum of 10 minutes

    const poll = setInterval(() => {
      this.http.get<{ status: string, video_url?: string, error?: string }>(apiUrl).subscribe({
        next: (response) => {
          if (response.status === 'completed') {
            this.video_url = response.video_url!;
            this.incrementProgress(25);
            this.updateProgress('Video generation complete.');
            this.finishLoading();
            clearInterval(poll);
            //this.handleAfterVideoGeneration();
          } else if (response.status === 'failed') {
            console.error('Video generation failed:', response.error);
            clearInterval(poll);
          } else {
            retries += 1;
            this.updateProgress(`Video status: ${response.status}...`);
            if (retries >= maxRetries) {
              console.error('Video generation is taking too long.');
              clearInterval(poll);
            }
          }
        },
        error: (err) => {
          console.error('Error polling task status:', err);
          this.finishLoading()
          clearInterval(poll);
        }
      });
    }, pollInterval);
  }

  // Centralized error handling function
  private handleError(message: string, error: any) {
    console.error(message, error);
    this.errorMessage = message;
    this.updateProgress(message); // Display error message in progress area
    this.finishLoading();
  }

  private generateStory(): Observable<ScriptResponse | undefined> {
    if (!this.storyTopic.trim()) {
      this.handleError('Please enter a topic for your motivational video.', new Error('No topic provided'));
      return of(undefined);
    }

    const apiUrl = this.getApiUrl('/video_motivation/get_motivational');
    const params = new HttpParams()
      .set('topic', this.storyTopic)
      .set('language', this.selectedLanguage);

    return this.http.get<ScriptResponse>(apiUrl, { params }).pipe(
      catchError((error) => {
        this.handleError('Failed to fetch the motivational script. Please try again.', error);
        return of(undefined);
      })
    );
  }

  private startLoading(): void {
    this.isLoading = true;
    this.progress = 0;
    this.progressMessage = '';
  }

  private updateProgress(message: string): void {
    this.progressMessage = message;
    this.cdr.detectChanges();
    console.log(message); // Optional: log progress messages for debugging
  }

  private incrementProgress(value: number): void {
    this.progress = Math.min(this.progress + value, 100);
  }

  private finishLoading(): void {
    this.progress = 100;
    setTimeout(() => {
      this.isLoading = false;
    }, 500);
  }


}
