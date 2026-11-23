import { ComponentFixture, TestBed } from '@angular/core/testing';

import { TranslateModule } from '@ngx-translate/core';
import { OverlayViewComponent } from './overlay-view.component';

describe('OverlayViewComponent', () => {
  let component: OverlayViewComponent;
  let fixture: ComponentFixture<OverlayViewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OverlayViewComponent, TranslateModule.forRoot()]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(OverlayViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
