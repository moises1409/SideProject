import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { VideoAnimationComponent } from './video-animation/video-animation.component';
import { VideoMotivationComponent } from './video-motivation/video-motivation.component';
import { VideoCommercialComponent } from "./video-commercial/video-commercial.component";
import { UsecasesLoaderComponent } from './usecases-loader/usecases-loader.component';


@Component({
  selector: 'app-root',
  standalone: true,
  imports: [UsecasesLoaderComponent],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  useCases = [
    { label: 'Video Animation', value: VideoAnimationComponent, id:'videoAnimation' },
    { label: 'Video Motivation', value: VideoMotivationComponent, id: 'videoMotivation' },
    { label: 'Video Commercial', value: VideoCommercialComponent, id:'videoCommercial' },
  ];
}

