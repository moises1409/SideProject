import { ComponentFixture, TestBed } from '@angular/core/testing';

import { UsecasesLoaderComponent } from './usecases-loader.component';

describe('UsecasesLoaderComponent', () => {
  let component: UsecasesLoaderComponent;
  let fixture: ComponentFixture<UsecasesLoaderComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [UsecasesLoaderComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(UsecasesLoaderComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
