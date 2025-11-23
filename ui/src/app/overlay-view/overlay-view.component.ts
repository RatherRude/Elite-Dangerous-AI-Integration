import { Component, OnDestroy, ElementRef, ViewChild, AfterViewInit } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
import { TauriService } from "../services/tauri.service";
import { Subscription } from "rxjs";
import { CommonModule } from "@angular/common";
import {PngTuberService} from "../services/pngtuber.service";
import {ChatMessage} from "../services/chat.service";
import {AvatarService} from "../services/avatar.service";
import {Character, CharacterService} from "../services/character.service";
import {Config, ConfigService} from "../services/config.service";

type ChatSegment = { text: string; color: string };
type OverlayChatEntry = ChatMessage & { segments: ChatSegment[] };

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
  chat: OverlayChatEntry[] = []
  characterColorMap: Record<string, string> = {};
  activeCharacters: {
    name: string;
    normalizedName: string;
    color: string;
    voice?: string;
    avatarId?: string;
    avatarUrl?: string | null;
  }[] = [];
  private avatarUrlCache: Record<string, string> = {};

  
  private currentAvatarUrl: string | null = null;
  private primaryAvatarUrl: string | null = null;
  speakingCharacterName: string | null = null;
  private subscriptions: Subscription[] = [];

  // Overlay display settings
  avatarPosition: 'left' | 'right' = 'right';
  avatarShow: boolean = true;
  chatShow: boolean = true;
  private isInitialized: boolean = false;

  constructor(
    private tauriService: TauriService,
    private pngTuberService: PngTuberService,
    private avatarService: AvatarService,
    private characterService: CharacterService,
    private configService: ConfigService,
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
        this.chat = preview.map(msg => ({
          ...msg,
          segments: this.formatMessageSegments(msg.message),
        }));
      })
    );
    
    // Subscribe to avatar URL changes from character service
    this.subscriptions.push(
      characterService.avatarUrl$.subscribe(avatarUrl => {
        this.primaryAvatarUrl = avatarUrl;
        if (!this.speakingCharacterName) {
          this.setCurrentAvatarUrl(avatarUrl);
        }
      })
    );

    // Track which character is currently speaking
    this.subscriptions.push(
      pngTuberService.speakingCharacter$.subscribe(activeSpeaker => {
        if (!activeSpeaker || !activeSpeaker.name) {
          this.speakingCharacterName = null;
          this.setCurrentAvatarUrl(this.primaryAvatarUrl);
          return;
        }
        this.speakingCharacterName = activeSpeaker.name;
        const avatarUrl = this.getAvatarUrlForName(activeSpeaker.name);
        if (avatarUrl) {
          this.setCurrentAvatarUrl(avatarUrl);
        } else {
          this.setCurrentAvatarUrl(this.primaryAvatarUrl);
        }
      })
    );

    // Subscribe to config changes to get overlay settings
    this.subscriptions.push(
      configService.config$.subscribe(config => {
        if (config) {
          this.avatarPosition = config.overlay_position || 'right';
          this.updateAvatarShowStatus(config);
          this.updateChatShowStatus(config);
          this.characterColorMap = this.buildCharacterColorMap(config);
          this.updateActiveCharacterInfo(config);
          this.reformatChatMessages();
          this.applyAvatarBackground(); // Update avatar when position changes
          this.isInitialized = true;
        } else if (!this.isInitialized) {
          // Reset to defaults if no character and not yet initialized
          this.avatarPosition = 'right';
          this.avatarShow = true;
          this.chatShow = true;
          this.activeCharacters = [];
          this.characterColorMap = {};
          this.applyAvatarBackground(); // Update avatar when resetting to defaults
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

  private formatMessageSegments(message: string): ChatSegment[] {
    const defaultColor = "#ffffff";
    const segments: ChatSegment[] = [];
    let currentColor = defaultColor;
    const regex = /\(([^)]+)\)/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = regex.exec(message)) !== null) {
      this.appendSegments(segments, message.slice(lastIndex, match.index), currentColor);

      const label = this.normalizeName(match[1]);
      currentColor = label && this.characterColorMap[label] ? this.characterColorMap[label] : defaultColor;
      lastIndex = regex.lastIndex;
    }

    this.appendSegments(segments, message.slice(lastIndex), currentColor);

    if (segments.length === 0) {
      segments.push({ text: "", color: defaultColor });
    }

    return segments;
  }

  private appendSegments(segments: ChatSegment[], rawText: string, color: string): void {
    if (!rawText) return;

    for (const part of rawText.split(/\r?\n/)) {
      const trimmed = part.trim();
      if (!trimmed) continue;
      segments.push({ text: trimmed, color });
    }
  }

  private buildCharacterColorMap(config: Config | null): Record<string, string> {
    const map: Record<string, string> = {};
    if (!config || !Array.isArray(config.characters)) {
      return map;
    }

    const activeIndexes = Array.isArray(config.active_characters) && config.active_characters.length > 0
      ? config.active_characters
      : (typeof config.active_character_index === "number" ? [config.active_character_index] : []);

    for (const idx of activeIndexes) {
      if (typeof idx !== "number") continue;
      const character = config.characters[idx] as Character | undefined;
      if (!character) continue;
      const normalizedName = this.normalizeName(character.name ?? `Character ${idx + 1}`);
      if (!normalizedName) continue;
      map[normalizedName] = this.normalizeColor(character.color);
    }

    return map;
  }

  private normalizeColor(value?: string): string {
    const trimmed = value?.trim();
    if (!trimmed) return "#ffffff";
    return trimmed.startsWith("#") ? trimmed : `#${trimmed}`;
  }

  private updateActiveCharacterInfo(config: Config | null): void {
    if (!config || !Array.isArray(config.characters)) {
      this.activeCharacters = [];
      return;
    }

    const activeIndexes = Array.isArray(config.active_characters) && config.active_characters.length > 0
      ? config.active_characters
      : (typeof config.active_character_index === "number" ? [config.active_character_index] : []);

    const infoList: typeof this.activeCharacters = [];
    for (const idx of activeIndexes) {
      if (typeof idx !== "number" || idx < 0 || idx >= config.characters.length) continue;
      const character = config.characters[idx] as Character | undefined;
      if (!character) continue;
      const avatarId = character.avatar ?? undefined;
      const displayName = character.name ?? `Character ${idx + 1}`;
      const info = {
        name: displayName,
        normalizedName: this.normalizeName(displayName),
        color: this.normalizeColor(character.color),
        voice: character.tts_voice,
        avatarId,
        avatarUrl: avatarId ? this.avatarUrlCache[avatarId] ?? null : null,
      };

      if (avatarId && !info.avatarUrl) {
        this.avatarService.getAvatar(avatarId).then(url => {
          if (url) {
            this.avatarUrlCache[avatarId] = url;
            info.avatarUrl = url;
            if (this.isCharacterSpeaking(info.name)) {
              this.setCurrentAvatarUrl(url);
            }
          }
        });
      }

      infoList.push(info);
    }

    this.activeCharacters = infoList;
    if (this.speakingCharacterName) {
      const avatar = this.getAvatarUrlForName(this.speakingCharacterName);
      if (avatar) {
        this.setCurrentAvatarUrl(avatar);
      } else {
        this.setCurrentAvatarUrl(this.primaryAvatarUrl);
      }
    }
  }

  private reformatChatMessages(): void {
    this.chat = this.chat.map(msg => ({
      ...msg,
      segments: this.formatMessageSegments(msg.message),
    }));
  }

  private normalizeName(value?: string | null): string {
    return (value ?? "").trim().toLowerCase();
  }

  public isCharacterSpeaking(name?: string): boolean {
    if (!name || !this.speakingCharacterName) {
      return false;
    }
    return this.normalizeName(name) === this.normalizeName(this.speakingCharacterName);
  }

  public getColorForName(name: string): string {
    const normalized = this.normalizeName(name);
    return this.characterColorMap[normalized] ?? "#ffffff";
  }

  private getAvatarUrlForName(name: string): string | null {
    const normalized = this.normalizeName(name);
    if (!normalized) return null;
    const match = this.activeCharacters.find(char => char.normalizedName === normalized);
    if (!match) return null;
    if (match.avatarUrl) {
      return match.avatarUrl;
    }
    if (match.avatarId && this.avatarUrlCache[match.avatarId]) {
      match.avatarUrl = this.avatarUrlCache[match.avatarId];
      return match.avatarUrl;
    }
    if (match.avatarId) {
      const avatarKey = match.avatarId;
      this.avatarService.getAvatar(avatarKey).then(url => {
        if (url) {
          this.avatarUrlCache[avatarKey] = url;
          match.avatarUrl = url;
          if (this.isCharacterSpeaking(match.name)) {
            this.setCurrentAvatarUrl(url);
          }
        }
      });
    }
    return null;
  }

  private setCurrentAvatarUrl(url: string | null): void {
    this.currentAvatarUrl = url;
    this.applyAvatarBackground();
  }
}
