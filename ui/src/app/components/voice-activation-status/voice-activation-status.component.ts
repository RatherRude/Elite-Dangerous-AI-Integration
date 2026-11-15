import { Component } from "@angular/core";
import { AsyncPipe } from "@angular/common";
import { TranslateModule } from "@ngx-translate/core";
import { VoiceActivationService } from "../../services/voice-activation.service";

@Component({
    selector: "app-voice-activation-status",
    standalone: true,
    imports: [AsyncPipe, TranslateModule],
    template: `
        @if (runtime.state$ | async; as state) {
            @if (state.state !== 'disabled') {
                <span role="status" aria-live="polite"
                    [class.active]="state.state === 'active'"
                    [class.error]="state.state === 'error'"
                    [attr.title]="state.warning || null">
                    {{ state.name }}: {{ ('voice.state.' + state.state) | translate }}
                </span>
            }
        }
    `,
    styles: [`
        :host { display: block; }
        span { display: inline-block; padding: 5px 10px; margin: 6px;
            border: 1px solid currentColor; border-radius: 12px; background: #171717;
            color: #bbb; font-size: 13px; }
        .active { color: var(--hud-cyan, #80cbc4); }
        .error { color: #ff8a80; }
    `],
})
export class VoiceActivationStatusComponent {
    constructor(public runtime: VoiceActivationService) {}
}
