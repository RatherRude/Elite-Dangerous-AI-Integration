import { Component, OnDestroy, OnInit } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import { TauriService } from "../services/tauri.service";
import { Subscription } from "rxjs";
import { CommonModule } from "@angular/common";
import {PngTuberService} from "../services/pngtuber.service";
import {ChatMessage, ChatService} from "../services/chat.service";

@Component({
  selector: "app-overlay-view",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./overlay-view.component.html",
  styleUrl: "./overlay-view.component.css",
})
export class OverlayViewComponent {
  action = 'idle'
  runMode = 'configuring'
  chat: ChatMessage[] = []

  constructor(
    private pngTuberService: PngTuberService,
    private chatService: ChatService
  ) {
    pngTuberService.runMode$.subscribe((mode)=>{
      this.runMode = mode
    });
    pngTuberService.action$.subscribe((action)=>{
      this.action = action
    });
    chatService.chat$.subscribe(chat=>{
      this.chat = chat.filter(value => ['covas', 'cmdr', 'action'].includes(value.role)).slice(-2)
    })

    // Make sure the background is transparent
    document.body.style.backgroundColor = "transparent";
    document.documentElement.style.backgroundColor = "transparent";
  }

  public getLogColor(role: string): string {
    switch (role.toLowerCase()) {
      case "error":
        return "red";
      case "warn":
        return "orange";
      case "info":
        return "#9C27B0";
      case "covas":
        return "#2196F3";
      case "event":
        return "#4CAF50";
      case "cmdr":
        return "#E91E63";
      case "action":
        return "#FF9800";
      default:
        return "inherit";
    }
  }
}
