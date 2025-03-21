import { Component, OnDestroy, OnInit } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import { TauriService } from "../services/tauri.service";
import { Subscription } from "rxjs";
import { CommonModule } from "@angular/common";

@Component({
  selector: "app-overlay-view",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./overlay-view.component.html",
  styleUrl: "./overlay-view.component.css",
})
export class OverlayViewComponent implements OnInit, OnDestroy {
  isRunning = false;
  isReady = false;
  private subscriptions: Subscription[] = [];

  constructor(
    private route: ActivatedRoute,
    private tauri: TauriService,
  ) {}

  ngOnInit() {
    // Subscribe to the running state
    this.tauri.runMode$.subscribe(
      (mode) => {
        this.isRunning = mode === "running";
        this.isReady = mode !== "starting";
      },
    );

    // Add the overlay-window class to the HTML element
    document.documentElement.classList.add("overlay-window");
    console.log("Overlay window initialized");

    // Directly hide any existing UI elements from the main app
    const mainElements = document.querySelectorAll(
      "main, mat-progress-bar, .container",
    );
    mainElements.forEach((element) => {
      if (element instanceof HTMLElement) {
        element.style.display = "none";
      }
    });

    // Make sure the background is transparent
    document.body.style.backgroundColor = "transparent";
    document.documentElement.style.backgroundColor = "transparent";
  }

  ngOnDestroy() {
    // Unsubscribe from all subscriptions
    this.subscriptions.forEach((sub) => sub.unsubscribe());

    // Remove the overlay-window class when the component is destroyed
    document.documentElement.classList.remove("overlay-window");
  }
}
