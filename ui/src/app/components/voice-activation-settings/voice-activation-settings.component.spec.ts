import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { TranslateLoader, TranslateModule, TranslateService } from "@ngx-translate/core";
import { InlineTranslateLoader } from "../../services/inline-translate-loader";
import { PARAKEET_GUID, PARAKEET_PROVIDER, VoiceActivationConfig } from "../../services/voice-activation.service";
import { VoiceActivationSettingsComponent } from "./voice-activation-settings.component";

describe("VoiceActivationSettingsComponent", () => {
    let fixture: ComponentFixture<VoiceActivationSettingsComponent>;
    const config: VoiceActivationConfig = {
        stt_provider: "remote", wake_word_timeout: 10,
        wake_word_source: "main", wake_word_first_command: "retranscribe",
    };

    beforeEach(async () => {
        await TestBed.configureTestingModule({
            imports: [VoiceActivationSettingsComponent, TranslateModule.forRoot({
                loader: { provide: TranslateLoader, useClass: InlineTranslateLoader },
            })],
            providers: [provideNoopAnimations()],
        }).compileComponents();
        TestBed.inject(TranslateService).use("en");
        fixture = TestBed.createComponent(VoiceActivationSettingsComponent);
        fixture.componentRef.setInput("name", "Simone");
        fixture.componentInstance.config = { ...config };
        fixture.detectChanges();
        await fixture.whenStable();
        fixture.detectChanges();
    });

    it("warns about remote standby transcription and recommends an optional plugin", () => {
        const text = fixture.nativeElement.textContent;
        expect(text).toContain("even in standby");
        expect(text).toContain("install the optional Parakeet plugin");
        expect(fixture.componentInstance.hybrid).toBeFalse();
    });

    it("shows the first-command choice only in an actual hybrid configuration", () => {
        const component = fixture.componentInstance;
        component.providers = [{
            plugin_guid: PARAKEET_GUID, id: "parakeet-stt", kind: "stt",
            label: "Parakeet (Local)", is_builtin: false, settings_config: [],
        }];
        component.config = { ...config, wake_word_source: "parakeet" };
        fixture.detectChanges();
        expect(component.hybrid).toBeTrue();
        expect(fixture.nativeElement.textContent).toContain("transcribed twice");
        component.config = { ...component.config, stt_provider: PARAKEET_PROVIDER };
        fixture.detectChanges();
        expect(component.hybrid).toBeFalse();
        expect(fixture.nativeElement.textContent).toContain("one transcription per phrase");
        expect(fixture.nativeElement.textContent).not.toContain("transcribed twice");
        expect(component.config.wake_word_first_command).toBe("retranscribe");
    });

    it("uses the avatar first name without exposing an editable global activation name", () => {
        const changed = jasmine.createSpy("configChange");
        fixture.componentInstance.configChange.subscribe(changed);
        const name: HTMLInputElement = fixture.nativeElement.querySelector('input[readonly]');
        expect(name.value).toBe("Simone");
        expect(fixture.nativeElement.querySelector('input:not([readonly]):not([type="number"])')).toBeNull();
        expect(fixture.nativeElement.textContent).toContain('Say "Simone"');
        expect(fixture.nativeElement.textContent).toContain("not its profile name");
        fixture.componentRef.setInput("name", "Astra");
        fixture.detectChanges();
        expect(name.value).toBe("Astra");
        expect(fixture.nativeElement.textContent).toContain('Say "Astra"');
        expect(fixture.nativeElement.textContent).not.toContain('Say "Simone"');
        expect(changed).not.toHaveBeenCalled();
    });

    it("uses the active avatar first name in the French instructions", async () => {
        TestBed.inject(TranslateService).use("fr");
        fixture.componentRef.setInput("name", "L\u00e9a Marie");
        fixture.detectChanges();
        await fixture.whenStable();
        fixture.detectChanges();
        expect(fixture.nativeElement.textContent).toContain("Dites « L\u00e9a Marie »");
        expect(fixture.nativeElement.textContent).toContain("communs \u00e0 tous les avatars");
    });

    it("does not send nonpositive timeouts to the backend", async () => {
        const changed = jasmine.createSpy("configChange");
        fixture.componentInstance.configChange.subscribe(changed);
        const timeout: HTMLInputElement = fixture.nativeElement.querySelector('input[type="number"]');
        timeout.value = "0";
        timeout.dispatchEvent(new Event("input"));
        timeout.dispatchEvent(new Event("blur"));
        fixture.detectChanges();
        await fixture.whenStable();
        fixture.detectChanges();
        expect(changed).not.toHaveBeenCalled();
        expect(fixture.nativeElement.textContent).toContain("greater than zero");
        timeout.value = "2.5";
        timeout.dispatchEvent(new Event("input"));
        fixture.detectChanges();
        expect(changed).toHaveBeenCalledWith({ wake_word_timeout: 2.5 });
    });
});
