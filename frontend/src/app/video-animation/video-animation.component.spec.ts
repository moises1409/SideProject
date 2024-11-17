import { ComponentFixture, TestBed } from '@angular/core/testing';

import { VideoAnimationComponent } from './video-animation.component';

describe('VideoAnimationComponent', () => {
  let component: VideoAnimationComponent;
  let fixture: ComponentFixture<VideoAnimationComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VideoAnimationComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(VideoAnimationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
