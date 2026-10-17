import { TestBed } from "@angular/core/testing";
import { BehaviorSubject } from "rxjs";
import { TranslateLoader, TranslateModule, TranslateService } from "@ngx-translate/core";
import { InlineTranslateLoader } from "../../services/inline-translate-loader";
import { VoiceActivationMessage, VoiceActivationService } from "../../services/voice-activation.service";
import { VoiceActivationStatusComponent } from "./voice-activation-status.component";

describe("VoiceActivationStatusComponent", () => {
    it("distinguishes standby and dialogue and disappears when disabled", async () => {
        const state = new BehaviorSubject<VoiceActivationMessage>({
            type: "voice_activation", name: "Simone", state: "standby", timestamp: "", index: 0,
        });
        await TestBed.configureTestingModule({
            imports: [VoiceActivationStatusComponent, TranslateModule.forRoot({
                loader: { provide: TranslateLoader, useClass: InlineTranslateLoader },
            })],
            providers: [{ provide: VoiceActivationService, useValue: { state$: state.asObservable() } }],
        }).compileComponents();
        TestBed.inject(TranslateService).use("en");
        const fixture = TestBed.createComponent(VoiceActivationStatusComponent);
        fixture.detectChanges();
        expect(fixture.nativeElement.textContent).toContain("Standby");
        state.next({ ...state.value, state: "active" });
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector(".active").textContent).toContain("Dialogue active");
        state.next({ ...state.value, state: "disabled" });
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector('[role="status"]')).toBeNull();
    });
});
