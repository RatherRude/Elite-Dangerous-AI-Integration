import { Component, OnDestroy, OnInit, ElementRef, ViewChild, AfterViewInit } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import { TauriService } from "../services/tauri.service";
import { Subscription } from "rxjs";
import { CommonModule } from "@angular/common";
import {PngTuberService} from "../services/pngtuber.service";
import {ChatMessage, ChatService} from "../services/chat.service";
import {AvatarService} from "../services/avatar.service";
import {CharacterService} from "../services/character.service";
import {Config, ConfigService} from "../services/config.service";

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
  private subscriptions: Subscription[] = [];

  // Overlay display settings
  avatarPosition: 'left' | 'right' = 'right';
  avatarShow: boolean = true;
  chatShow: boolean = true;
  private isInitialized: boolean = false;

  constructor(
    private tauriService: TauriService,
    private pngTuberService: PngTuberService,
    private chatService: ChatService,
    private avatarService: AvatarService,
    private characterService: CharacterService,
    private configService: ConfigService
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
      pngTuberService.chatPreview$.subscribe(preview=>{
        this.chat = preview;
      })
    );
    
    // Subscribe to avatar URL changes from character service
    this.subscriptions.push(
      characterService.avatarUrl$.subscribe(avatarUrl => {
        this.currentAvatarUrl = avatarUrl;
        this.applyAvatarBackground();
      })
    );

    // Subscribe to config changes to get overlay settings
    this.subscriptions.push(
      configService.config$.subscribe(config => {
        if (config) {
          this.avatarPosition = config.overlay_position || 'right';
          this.updateAvatarShowStatus(config);
          this.updateChatShowStatus(config);
          this.applyAvatarBackground(); // Update avatar when position changes
          this.isInitialized = true;
        } else if (!this.isInitialized) {
          // Reset to defaults if no character and not yet initialized
          this.avatarPosition = 'right';
          this.avatarShow = true;
          this.chatShow = true;
          this.applyAvatarBackground(); // Update avatar when resetting to defaults
        }
      })
    );

    // Subscribe to config changes to update overlay visibility settings
    this.subscriptions.push(
      configService.config$.subscribe(config => {
        if (config) {
          this.updateAvatarShowStatus(config);
          this.updateChatShowStatus(config);
        }
      })
    );

    // Make sure the background is transparent
    document.body.style.backgroundColor = "transparent";
    document.documentElement.style.backgroundColor = "transparent";
  }
  
  ngAfterViewInit() {
    // Apply avatar background if we have one
    if (this.currentAvatarUrl) {
      this.applyAvatarBackground();
    }
    this.tauriService.send_command({
      type: "init_overlay",
      timestamp: new Date().toISOString(),
      index:0,
    })
  }
  
  ngOnDestroy() {
    // Clean up subscriptions
    this.subscriptions.forEach(sub => sub.unsubscribe());
    
    // Clean up avatar URL
    if (this.currentAvatarUrl) {
      URL.revokeObjectURL(this.currentAvatarUrl);
    }
  }
  
  private updateAvatarShowStatus(config: Config): void {
    // Use global overlay setting
    this.avatarShow = config?.overlay_show_avatar !== false && config?.tts_provider !== 'none';
  }

  private updateChatShowStatus(config: Config): void {
    // Use global overlay setting for chat
    this.chatShow = config?.overlay_show_chat !== false && config?.tts_provider !== 'none';
  }

  private applyAvatarBackground() {
    // Wait for next tick to ensure view is rendered, with longer timeout for *ngIf changes
    setTimeout(() => {
      // Only apply if avatar should be shown and element exists
      if (this.avatarShow && this.pngtuberElement?.nativeElement) {
        if (this.currentAvatarUrl) {
          this.pngtuberElement.nativeElement.style.backgroundImage = `url('${this.currentAvatarUrl}')`;
        } else {
          // Use flipped default avatar when overlay position is left
          const defaultAvatar = this.avatarPosition === 'left' 
            ? 'assets/cn_avatar_default_flipped.png' 
            : 'assets/cn_avatar_default.png';
          this.pngtuberElement.nativeElement.style.backgroundImage = `url('${defaultAvatar}')`;
        }
      }
    }, 10); // Slightly longer timeout to handle *ngIf rendering
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
