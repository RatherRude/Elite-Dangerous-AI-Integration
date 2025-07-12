import { Component, OnDestroy, OnInit, ElementRef, ViewChild, AfterViewInit } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import { TauriService } from "../services/tauri.service";
import { Subscription } from "rxjs";
import { CommonModule } from "@angular/common";
import {PngTuberService} from "../services/pngtuber.service";
import {ChatMessage, ChatService} from "../services/chat.service";
import {AvatarService} from "../services/avatar.service";
import {CharacterService} from "../services/character.service";
import {ConfigService} from "../services/config.service";

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

  // Avatar positioning and flip settings
  avatarPosition: 'left' | 'right' = 'right';
  avatarFlip: boolean = false;
  avatarShow: boolean = true;
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
      chatService.chat$.subscribe(chat=>{
        this.chat = chat.filter(value => ['covas', 'cmdr', 'action'].includes(value.role)).slice(-2)
      })
    );
    
    // Subscribe to avatar URL changes from character service
    this.subscriptions.push(
      characterService.avatarUrl$.subscribe(avatarUrl => {
        this.currentAvatarUrl = avatarUrl;
        this.applyAvatarBackground();
      })
    );

    // Subscribe to character changes to get avatar settings
    this.subscriptions.push(
      characterService.character$.subscribe(character => {
        if (character) {
          this.avatarPosition = character.avatar_position || 'right';
          this.avatarFlip = character.avatar_flip || false;
          this.updateAvatarShowStatus(character);
          this.isInitialized = true;
        } else if (!this.isInitialized) {
          // Reset to defaults if no character and not yet initialized
          this.avatarPosition = 'right';
          this.avatarFlip = false;
          this.avatarShow = true;
        }
      })
    );

    // Subscribe to config changes to update avatar visibility based on EDCP settings
    this.subscriptions.push(
      configService.config$.subscribe(config => {
        const character = this.characterService.getCurrentCharacter();
        if (character && config) {
          this.updateAvatarShowStatus(character, config);
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
  
  private updateAvatarShowStatus(character: any, config?: any): void {
    const currentConfig = config || this.configService.getCurrentConfig();
    
    // Hide avatar if EDCP is enabled and dominant
    const isEDCPDominant = currentConfig?.edcopilot === true && currentConfig?.edcopilot_dominant === true;
    
    if (isEDCPDominant) {
      this.avatarShow = false;
    } else {
      // Default to true if avatar_show is undefined, only false if explicitly set to false
      this.avatarShow = character?.avatar_show !== false;
    }
  }

  private applyAvatarBackground() {
    // Wait for next tick to ensure view is rendered, with longer timeout for *ngIf changes
    setTimeout(() => {
      // Only apply if avatar should be shown and element exists
      if (this.avatarShow && this.pngtuberElement?.nativeElement) {
        if (this.currentAvatarUrl) {
          this.pngtuberElement.nativeElement.style.backgroundImage = `url('${this.currentAvatarUrl}')`;
        } else {
          // Revert to CSS default background image when no avatar URL
          this.pngtuberElement.nativeElement.style.backgroundImage = '';
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
