import { Component, OnDestroy, ElementRef, ViewChild, AfterViewInit } from "@angular/core";
import { DomSanitizer, SafeHtml } from "@angular/platform-browser";
import { TauriService } from "../services/tauri.service";
import { Subscription, combineLatest } from "rxjs";
import { CommonModule } from "@angular/common";
import {PngTuberService} from "../services/pngtuber.service";
import {ChatMessage, ChatService} from "../services/chat.service";
import {AvatarService} from "../services/avatar.service";
import {CharacterService} from "../services/character.service";
import {Config, ConfigService} from "../services/config.service";
import {GenUiRenderComponent} from "../components/gen-ui-render/gen-ui-render.component";
import { EventService } from "../services/event.service";

@Component({
  selector: "app-overlay-view",
  standalone: true,
  imports: [CommonModule, GenUiRenderComponent],
  templateUrl: "./overlay-view.component.html",
  styleUrl: "./overlay-view.component.css",
})
export class OverlayViewComponent implements OnDestroy, AfterViewInit {
  @ViewChild('pngtuberElement', { static: false }) pngtuberElement?: ElementRef<HTMLDivElement>;

  action = 'idle'
  runMode = 'configuring'
  chat: ChatMessage[] = []

  /** Injected SVG markup; state classes live on `.overlay-svg-tuber` (see cn_avatar.svg). */
  sanitizedSvg: SafeHtml | null = null;

  private currentAvatarUrl: string | null = null;
  private baseAvatarUrl: string | null = null;
  private baseAvatarMime: string | null = null;
  private scriptedAvatarUrl: string | null = null;
  private scriptedAvatarMime: string | null = null;
  private scriptedAvatarId: string | null = null;
  private scriptedAvatarRequestSeq = 0;
  private svgFetchSeq = 0;
  private subscriptions: Subscription[] = [];

  // Overlay display settings
  avatarPosition: 'left' | 'right' = 'right';
  avatarScale: number = 1;
  readonly avatarBaseWidth = 250;
  avatarShow: boolean = true;
  chatShow: boolean = true;
  private isInitialized: boolean = false;

  constructor(
    private tauriService: TauriService,
    private pngTuberService: PngTuberService,
    private chatService: ChatService,
    private avatarService: AvatarService,
    private characterService: CharacterService,
    private configService: ConfigService,
    private eventService: EventService,
    private sanitizer: DomSanitizer,
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
    
    // Keep URL + MIME in sync (PNG sprite vs inline SVG)
    this.subscriptions.push(
      combineLatest([characterService.avatarUrl$, characterService.avatarMime$]).subscribe(
        ([avatarUrl, mime]) => {
          this.baseAvatarUrl = avatarUrl;
          this.baseAvatarMime = mime;
          if (!this.scriptedAvatarUrl) {
            this.currentAvatarUrl = avatarUrl;
          }
          this.refreshAvatarDisplay();
        },
      ),
    );
    this.subscriptions.push(
      chatService.chatMessage$.subscribe((msg) => {
        if (!msg) {
          return;
        }
        if (msg.role === "npc_message") {
          void this.setScriptedAvatar(msg.avatar_id ?? msg.avatar_url);
        }
      }),
    );
    this.subscriptions.push(
      eventService.events$.subscribe((messages) => {
        const message = messages.at(-1);
        if (!message) {
          return;
        }
        if (message.event.kind === "assistant_completed") {
          this.clearScriptedAvatar();
        }
      }),
    );

    // Subscribe to config changes to get overlay settings
    this.subscriptions.push(
      configService.config$.subscribe(config => {
        if (config) {
          this.setAvatarDisplayFromPosition(config.overlay_position || 'right');
          this.updateAvatarShowStatus(config);
          this.updateChatShowStatus(config);
          this.refreshAvatarDisplay();
          this.isInitialized = true;
        } else if (!this.isInitialized) {
          // Reset to defaults if no character and not yet initialized
          this.setAvatarDisplayFromPosition('right');
          this.avatarShow = true;
          this.chatShow = true;
          this.refreshAvatarDisplay();
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
    this.refreshAvatarDisplay();
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
    if (this.currentAvatarUrl && this.avatarService.isObjectUrl(this.currentAvatarUrl)) {
      URL.revokeObjectURL(this.currentAvatarUrl);
    }
  }
  
  private updateAvatarShowStatus(config: Config): void {
    // Use global overlay setting
    this.avatarShow = true;
    if (config?.overlay_show_avatar === false) {
      this.avatarShow = false;
    }
    if (config?.tts_provider === 'none') {
      this.avatarShow = false;
    }
    if (config?.tts_provider === 'plugin:ec3eee66-8c4c-4ede-be36-b8612b14a5c0:edcopilot-dominant') {
      this.avatarShow = false;
    }
  }

  private updateChatShowStatus(config: Config): void {
    // Use global overlay setting for chat
    this.chatShow = true;
    if (config?.overlay_show_chat === false) {
      this.chatShow = false;
    } 
    if (config?.tts_provider === 'none') {
      this.chatShow = false;
    }
    if (config?.tts_provider === 'plugin:ec3eee66-8c4c-4ede-be36-b8612b14a5c0:edcopilot-dominant') {
      this.chatShow = false;
    }
  }

  /** SVG avatars are embedded so internal style state selectors (e.g. `.listening .eye-base`) apply. */
  get avatarUsesInlineSvg(): boolean {
    return this.effectiveAvatarMimePrimary() === "image/svg+xml";
  }

  /** SVG defines listening | speaking | thinking | acting — map idle to listening. */
  get svgAnimationClass(): string {
    return this.action === "idle" ? "listening" : this.action;
  }

  private effectiveAvatarMimePrimary(): string | null {
    if (!this.currentAvatarUrl) {
      return null;
    }
    const mime = this.scriptedAvatarUrl ? this.scriptedAvatarMime : this.baseAvatarMime;
    if (!mime) {
      return null;
    }
    return mime.trim().toLowerCase().split(";")[0]?.trim() ?? null;
  }

  private setAvatarDisplayFromPosition(position: Config['overlay_position'] | string): void {
    const [side, size = 'large'] = position.split("-");
    this.avatarPosition = side === 'left' ? 'left' : 'right';
    switch (size) {
      case 'small':
        this.avatarScale = 0.5;
        break;
      case 'medium':
        this.avatarScale = 0.75;
        break;
      default:
        this.avatarScale = 1;
        break;
    }
  }

  private refreshAvatarDisplay(): void {
    setTimeout(() => {
      if (!this.avatarShow) {
        return;
      }
      const url = this.currentAvatarUrl;
      if (this.avatarUsesInlineSvg && url) {
        void this.loadInlineSvg(url);
        return;
      }
      this.svgFetchSeq += 1;
      this.sanitizedSvg = null;
      this.applyPngTuberBackground();
    }, 10);
  }

  private applyPngTuberBackground(): void {
    const el = this.pngtuberElement?.nativeElement;
    if (!this.avatarShow || !el) {
      return;
    }
    if (this.currentAvatarUrl) {
      el.style.backgroundImage = `url('${this.currentAvatarUrl}')`;
    } else {
      const defaultAvatar =
        this.avatarPosition === "left"
          ? "assets/cn_avatar_default_flipped.png"
          : "assets/cn_avatar_default.png";
      el.style.backgroundImage = `url('${defaultAvatar}')`;
    }
  }

  private async loadInlineSvg(url: string): Promise<void> {
    const seq = ++this.svgFetchSeq;
    try {
      const res = await fetch(url);
      const text = await res.text();
      if (
        seq !== this.svgFetchSeq ||
        url !== this.currentAvatarUrl ||
        this.effectiveAvatarMimePrimary() !== "image/svg+xml"
      ) {
        return;
      }
      const safe = this.stripScriptsFromSvg(this.stripSvgRootClass(text));
      this.sanitizedSvg = this.sanitizer.bypassSecurityTrustHtml(safe);
    } catch (err) {
      console.error("Overlay: failed to load SVG avatar", err);
      if (seq === this.svgFetchSeq) {
        this.sanitizedSvg = null;
      }
    }
  }

  private stripSvgRootClass(svg: string): string {
    return svg.replace(/<svg\b([^>]*)>/i, (_m, attrs: string) => {
      const next = attrs
        .replace(/\sclass\s*=\s*"[^"]*"/gi, "")
        .replace(/\sclass\s*=\s*'[^']*'/gi, "")
        .trim();
      return next ? `<svg ${next}>` : "<svg>";
    });
  }

  private stripScriptsFromSvg(svg: string): string {
    return svg.replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "");
  }

  private async setScriptedAvatar(avatarRef?: string): Promise<void> {
    if (!avatarRef) {
      this.clearScriptedAvatar();
      return;
    }
    if (this.scriptedAvatarId === avatarRef && this.scriptedAvatarUrl) {
      return;
    }
    const requestSeq = ++this.scriptedAvatarRequestSeq;
    try {
      const meta = await this.avatarService.getAvatarWithMime(avatarRef);
      if (requestSeq !== this.scriptedAvatarRequestSeq) {
        if (meta?.url && this.avatarService.isObjectUrl(meta.url)) {
          URL.revokeObjectURL(meta.url);
        }
        return;
      }
      if (!meta?.url) {
        this.clearScriptedAvatar();
        return;
      }
      if (
        this.scriptedAvatarUrl &&
        this.scriptedAvatarUrl !== meta.url &&
        this.avatarService.isObjectUrl(this.scriptedAvatarUrl)
      ) {
        URL.revokeObjectURL(this.scriptedAvatarUrl);
      }
      this.scriptedAvatarId = avatarRef;
      this.scriptedAvatarUrl = meta.url;
      this.scriptedAvatarMime = meta.mimeType;
      this.currentAvatarUrl = meta.url;
      this.refreshAvatarDisplay();
    } catch (error) {
      console.error("Error loading scripted dialog avatar:", error);
      this.clearScriptedAvatar();
    }
  }

  private clearScriptedAvatar(): void {
    this.scriptedAvatarRequestSeq += 1;
    this.scriptedAvatarId = null;
    this.scriptedAvatarMime = null;
    if (this.scriptedAvatarUrl && this.avatarService.isObjectUrl(this.scriptedAvatarUrl)) {
      URL.revokeObjectURL(this.scriptedAvatarUrl);
    }
    this.scriptedAvatarUrl = null;
    this.currentAvatarUrl = this.baseAvatarUrl;
    this.refreshAvatarDisplay();
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
      case "npc_message":
        return "#2196F3";
      default:
        return "inherit";
    }
  }
}
