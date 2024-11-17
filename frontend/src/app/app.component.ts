import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { VideoGenerationComponent } from './video-generation/video-generation.component';
import { VideoAnimationComponent } from './video-animation/video-animation.component';
import { VideoMotivationComponent } from './video-motivation/video-motivation.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [VideoGenerationComponent, VideoAnimationComponent, VideoMotivationComponent],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'frontend';
}

