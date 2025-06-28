import { Component, OnDestroy, OnInit } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import { TauriService } from "../services/tauri.service";
import { Subscription } from "rxjs";
import { CommonModule } from "@angular/common";
import {PngTuberService} from "../services/pngtuber.service";

@Component({
  selector: "app-overlay-view",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./overlay-view.component.html",
  styleUrl: "./overlay-view.component.css",
})
export class OverlayViewComponent {
  action = 'thinking'
  runMode = 'configuring'

  constructor(
    private pngTuberService: PngTuberService,
  ) {
    pngTuberService.runMode$.subscribe((mode)=>{
      this.runMode = mode
    });
    pngTuberService.action$.subscribe((action)=>{
      this.action = action
    });

    // Make sure the background is transparent
    document.body.style.backgroundColor = "transparent";
    document.documentElement.style.backgroundColor = "transparent";
  }
}
