import { Component, OnDestroy, OnInit, ElementRef, ViewChild, AfterViewInit } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import { TauriService } from "../services/tauri.service";
import { Subscription } from "rxjs";
import { CommonModule } from "@angular/common";
import {PngTuberService} from "../services/pngtuber.service";
import {ChatMessage, ChatService} from "../services/chat.service";
import {AvatarService} from "../services/avatar.service";

@Component({
  selector: "app-overlay-view",
  standalone: true,
  imports: [CommonModule],
  templateUrl: "./overlay-view.component.html",
  styleUrl: "./overlay-view.component.css",
})
export class OverlayViewComponent implements OnDestroy, AfterViewInit {
  @ViewChild('pngtuberElement', { static: false }) pngtuberElement!: ElementRef<HTMLDivElement>;
  
  action = 'idle'
  runMode = 'configuring'
  chat: ChatMessage[] = []
  
  private currentAvatarUrl: string | null = null;
  private avatarId: string | null = null;
  private subscriptions: Subscription[] = [];

  constructor(
    private pngTuberService: PngTuberService,
    private chatService: ChatService,
    private avatarService: AvatarService
  ) {
    // Subscribe to run mode changes
    this.subscriptions.push(
      pngTuberService.runMode$.subscribe((mode)=>{
        this.runMode = mode
      })
    );
    
    // Subscribe to action changes
    this.subscriptions.push(
      pngTuberService.action$.subscribe((action)=>{
        this.action = action
      })
    );
    
    // Subscribe to chat changes
    this.subscriptions.push(
      chatService.chat$.subscribe(chat=>{
        this.chat = chat.filter(value => ['covas', 'cmdr', 'action'].includes(value.role)).slice(-2)
      })
    );
    
    // Subscribe to avatar ID changes
    this.subscriptions.push(
      pngTuberService.avatarId$.subscribe(avatarId => {
        this.avatarId = avatarId;
        // Load avatar immediately when it changes, regardless of run mode
        this.loadAvatar();
      })
    );

    // Make sure the background is transparent
    document.body.style.backgroundColor = "transparent";
    document.documentElement.style.backgroundColor = "transparent";
  }
  
  ngAfterViewInit() {
    // Load avatar on initial view render if we have one
    if (this.avatarId) {
      this.loadAvatar();
    }
  }
  
  ngOnDestroy() {
    // Clean up subscriptions
    this.subscriptions.forEach(sub => sub.unsubscribe());
    
    // Clean up avatar URL
    if (this.currentAvatarUrl) {
      URL.revokeObjectURL(this.currentAvatarUrl);
    }
  }
  
  private async loadAvatar() {
    // Clean up previous avatar URL
    if (this.currentAvatarUrl) {
      URL.revokeObjectURL(this.currentAvatarUrl);
      this.currentAvatarUrl = null;
    }
    
    if (!this.avatarId) {
      // Revert to default fallback image when no avatar is set
      this.applyDefaultBackground();
      return;
    }
    
    try {
      this.currentAvatarUrl = await this.avatarService.getAvatar(this.avatarId);
      this.applyAvatarBackground();
    } catch (error) {
      console.error('Error loading avatar for overlay:', error);
      // Fallback to default on error
      this.applyDefaultBackground();
    }
  }
  
  private applyAvatarBackground() {
    // Wait for next tick to ensure view is rendered
    setTimeout(() => {
      if (this.pngtuberElement && this.currentAvatarUrl) {
        this.pngtuberElement.nativeElement.style.backgroundImage = `url('${this.currentAvatarUrl}')`;
      }
    }, 0);
  }
  
  private applyDefaultBackground() {
    // Revert to CSS default background image
    setTimeout(() => {
      if (this.pngtuberElement) {
        this.pngtuberElement.nativeElement.style.backgroundImage = '';
      }
    }, 0);
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
