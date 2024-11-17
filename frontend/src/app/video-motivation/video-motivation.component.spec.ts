import { ComponentFixture, TestBed } from '@angular/core/testing';

import { VideoMotivationComponent } from './video-motivation.component';

describe('VideoMotivationComponent', () => {
  let component: VideoMotivationComponent;
  let fixture: ComponentFixture<VideoMotivationComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VideoMotivationComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(VideoMotivationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
