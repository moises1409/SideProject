import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { VideoAnimationComponent } from './video-animation/video-animation.component';
import { VideoMotivationComponent } from './video-motivation/video-motivation.component';
import { VideoCommercialComponent } from "./video-commercial/video-commercial.component";

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [VideoAnimationComponent, VideoMotivationComponent, VideoCommercialComponent],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'frontend';
}

