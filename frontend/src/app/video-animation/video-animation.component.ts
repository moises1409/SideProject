import { Component, ChangeDetectorRef } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { HttpClientModule } from '@angular/common/http';
import { of, Observable, forkJoin, interval, throwError } from 'rxjs';
import { catchError, map, switchMap, takeWhile } from 'rxjs/operators';

interface StoryResponse {
  complete_story: string;
  scenes: Array<{
    image_prompt: string;
    sentences: string;
  }>;
}

@Component({
  selector: 'app-video-animation',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './video-animation.component.html',
  styleUrl: './video-animation.component.css'
})

export class VideoAnimationComponent {
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

  // Function to call after the video has been successfully generated
  private handleAfterVideoGeneration(): void {
    const audioUrls = this.generatedResults.map(([image, audio]) => audio); // Extract audio URLs from generatedResults
    this.deleteAudioFiles(audioUrls);
  }
  // Main function with error handling
  mainFunction(): void {
    this.startLoading();
    this.updateProgress('Generating story...');
    this.generateStory()
      .pipe(
        catchError((error) => {
          this.handleError('Failed to generate the story. Please try again later.', error);
          return throwError(() => error); // Stop further execution
        })
      )
      .subscribe({
        next: (response) => {
          if (response) {
            console.log('The Story has been generated:', response.complete_story);
            this.incrementProgress(25);
            this.handleSceneGeneration(response.scenes);
          } else {
            this.finishLoading();
          }
        },
        error: () => this.finishLoading(),
      });
  }

  // Function to handle scene generation with error handling
  private handleSceneGeneration(scenes: Array<{ image_prompt: string; sentences: string }>) {
    const sceneRequests = scenes.map((scene, index) => {
      this.updateProgress(`Generating image and audio ...`);
      return forkJoin({
        image: this.generateImage(scene.image_prompt),
        //audio: this.generateAudio(scene.sentences),
      }).pipe(
        catchError((error) => {
          this.handleError('Error generating image and audio. Please try again later.', error);
          return throwError(() => error);
        }),
        map((result) => [result.image, scene.sentences] as [string, string])
      );
    });

    forkJoin(sceneRequests)
      .pipe(
        catchError((error) => {
          this.handleError('Error generating scenes. Please try again later.', error);
          return throwError(() => error);
        })
      )
      .subscribe({
        next: (results) => {
          this.generatedResults = results.filter(
            (result) => result[0] !== undefined && result[1] !== undefined
          ) as [string, string][];
          console.log('Generated Results:', this.generatedResults);
          this.incrementProgress(25);
          this.generateVideo();
        },
        error: () => this.finishLoading(),
      });
  } 

  // Function to generate the video and handle errors
  private generateVideo() {
    this.updateProgress('Generating video...');
    const apiUrl = this.getApiUrl('/animated_story/video_animated_editor');
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

  private generateStory(): Observable<StoryResponse | undefined> {
    if (!this.storyTopic.trim()) {
      this.handleError('Please enter a topic for your story.', new Error('No topic provided'));
      return of(undefined);
    }

    const apiUrl = this.getApiUrl('/animated_story/get_story');
    const params = new HttpParams()
      .set('topic', this.storyTopic)
      .set('language', this.selectedLanguage);

    return this.http.get<StoryResponse>(apiUrl, { params }).pipe(
      catchError((error) => {
        this.handleError('Failed to fetch the story. Please try again.', error);
        return of(undefined);
      })
    );
  }

  generateImage(parameter: string): Observable<string | undefined> {
    const apiUrl = this.getApiUrl('/generic_apis/get_image');
    const params = new HttpParams().set('prompt', parameter);

    return this.http.get(apiUrl, { params, responseType: 'text' }).pipe(
      catchError((error) => {
        this.handleError('Error fetching image URL.', error);
        return of(undefined);
      })
    );
  }

  generateAudio(parameter: string): Observable<string | undefined> {
    const apiUrl = this.getApiUrl('/generic_apis/get_audio');
    const params = new HttpParams()
      .set('text', parameter)
      .set('language', this.selectedLanguage);

    return this.http.get(apiUrl, { params, responseType: 'text' }).pipe(
      catchError((error) => {
        this.handleError('Error fetching audio URL.', error);
        return of(undefined);
      })
    );
  }

  // Function to call the Python API to delete audio files
  private deleteAudioFiles(audioUrls: string[]): void {
    const apiUrl = this.getApiUrl('/generic_apis/delete_audio_files'); // Ensure this matches your backend URL
    const headers = new HttpHeaders({ 'Content-Type': 'application/json' });
    const body = { audio_urls: audioUrls };

    this.http.post(apiUrl, body, { headers }).subscribe({
      next: (response) => {
        console.log('Audio files deleted successfully:', response);
      },
      error: (error) => {
        console.error('Error deleting audio files:', error);
        this.errorMessage = 'Failed to delete audio files.';
      },
    });
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
