import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { VideoGenerationComponent } from './video-generation/video-generation.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, VideoGenerationComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent {
  title = 'frontend';
}
