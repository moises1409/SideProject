import { ComponentFixture, TestBed } from '@angular/core/testing';

import { VideoCommercialComponent } from './video-commercial.component';

describe('VideoCommercialComponent', () => {
  let component: VideoCommercialComponent;
  let fixture: ComponentFixture<VideoCommercialComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [VideoCommercialComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(VideoCommercialComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
