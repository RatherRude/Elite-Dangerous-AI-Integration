import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { MatSnackBar } from "@angular/material/snack-bar";
import { AvatarService } from "../../services/avatar.service";
import { ConfigWithCharacters } from "../../services/character.service";
import { ConfigService } from "../../services/config.service";
import { CrewRosterComponent } from "./crew-roster.component";
import { BehaviorSubject } from "rxjs";
import { ModelProviderDefinition } from "../../services/plugin-settings";

describe("CrewRosterComponent", () => {
    let fixture: ComponentFixture<CrewRosterComponent>;
    let component: CrewRosterComponent;
    let configService: jasmine.SpyObj<ConfigService>;
    let avatarService: jasmine.SpyObj<AvatarService>;
    let snackBar: jasmine.SpyObj<MatSnackBar>;
    let providers$: BehaviorSubject<ModelProviderDefinition[]>;

    beforeEach(async () => {
        providers$ = new BehaviorSubject<ModelProviderDefinition[]>([]);
        configService = jasmine.createSpyObj("ConfigService", ["changeConfig"], {
            plugin_model_providers$: providers$, pluginCharacters$: new BehaviorSubject([]),
        });
        configService.changeConfig.and.resolveTo();
        avatarService = jasmine.createSpyObj("AvatarService", ["getAvatarWithMime", "isObjectUrl"]);
        avatarService.getAvatarWithMime.and.resolveTo(null);
        avatarService.isObjectUrl.and.callFake((url) => Boolean(url?.startsWith("blob:")));
        snackBar = jasmine.createSpyObj("MatSnackBar", ["open"]);
        await TestBed.configureTestingModule({
            imports: [CrewRosterComponent, NoopAnimationsModule],
            providers: [
                { provide: ConfigService, useValue: configService },
                { provide: AvatarService, useValue: avatarService },
                { provide: MatSnackBar, useValue: snackBar },
            ],
        }).compileComponents();
        fixture = TestBed.createComponent(CrewRosterComponent);
        component = fixture.componentInstance;
        fixture.componentRef.setInput("config", {
            characters: [{ name: "COVAS", tts_voice: "alloy" }, { name: "Nyx", tts_voice: "nova" }, { name: "Orion", tts_voice: "echo" }],
            active_character_index: 0,
            active_characters: [0, 1],
        } as ConfigWithCharacters);
        fixture.detectChanges();
    });

    it("shows active portraits and keeps standby management collapsed", () => {
        expect(fixture.nativeElement.querySelectorAll(".crew-card").length).toBe(2);
        expect(fixture.nativeElement.querySelector(".crew-primary-star")).not.toBeNull();
        expect(fixture.nativeElement.querySelector("#standby-roster")).toBeNull();
        expect(fixture.nativeElement.querySelector(".crew-header button").textContent).toContain("Modify Crew Roster");
    });

    it("reveals standby characters and disables removal of the primary", () => {
        fixture.nativeElement.querySelector(".crew-header button").click();
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector("#standby-roster").textContent).toContain("Orion");
        expect(fixture.nativeElement.querySelector(".crew-card--primary .crew-standby-action").disabled).toBeTrue();
    });

    it("notifies the parent when roster management opens and closes", () => {
        const changed = spyOn(component.rosterManagerChanged, "emit");
        fixture.nativeElement.querySelector(".crew-header button").click();
        fixture.detectChanges();
        expect(changed).toHaveBeenCalledWith(true);
        fixture.nativeElement.querySelector(".crew-header button").click();
        fixture.detectChanges();
        expect(changed).toHaveBeenCalledWith(false);
    });

    it("saves crew membership without changing the primary or other config", async () => {
        await component.setCrewMember(2, true);
        expect(configService.changeConfig).toHaveBeenCalledOnceWith({ active_characters: [0, 1, 2] });
    });

    it("moves support crew to standby", async () => {
        await component.setCrewMember(1, false);
        expect(configService.changeConfig).toHaveBeenCalledOnceWith({ active_characters: [0] });
    });

    it("uses the lower avatar overlay to move a character to standby without changing primary", async () => {
        component.toggleRosterManager();
        fixture.detectChanges();
        const selected = spyOn(component.primarySelected, "emit");
        const activeCards = fixture.nativeElement.querySelectorAll('[aria-label="Active crew"] .crew-card');
        expect(activeCards[1].querySelector(".crew-membership-button")).toBeNull();
        const overlay = activeCards[1].querySelector(".crew-standby-action");
        expect(overlay.textContent).toContain("arrow_downward");
        expect(overlay.textContent).toContain("Standby");
        overlay.click();
        await fixture.whenStable();
        expect(configService.changeConfig).toHaveBeenCalledOnceWith({ active_characters: [0] });
        expect(selected).not.toHaveBeenCalled();
    });

    it("requests editing from both active and standby pencils without selecting them", () => {
        component.toggleRosterManager();
        fixture.detectChanges();
        const edit = spyOn(component.characterEditRequested, "emit");
        const selected = spyOn(component.primarySelected, "emit");
        const pencils = fixture.nativeElement.querySelectorAll(".crew-edit-button");
        expect(pencils[0].disabled).toBeTrue();
        pencils[1].click();
        expect(edit).toHaveBeenCalledWith(1);
        pencils[2].click();
        expect(edit).toHaveBeenCalledWith(2);
        expect(selected).not.toHaveBeenCalled();
    });

    it("shows voices rather than primary/support role labels", () => {
        const voices = fixture.nativeElement.querySelectorAll(".crew-voice");
        expect(voices[0].textContent).toBe("alloy");
        expect(voices[1].textContent).toBe("nova");
        expect(fixture.nativeElement.querySelector(".crew-role")).toBeNull();
    });

    it("displays the selected provider's per-character voice label", () => {
        providers$.next([{
            plugin_guid: "voice-plugin", id: "tts", kind: "tts",
            voice_settings_config: [{ key: "voice", fields: [{
                key: "voice", type: "select", select_options: [{ value: "sample", label: "Sample Voice" }],
            }] }],
        } as ModelProviderDefinition]);
        fixture.componentRef.setInput("config", {
            ...component.config, tts_provider: "plugin:voice-plugin:tts",
            characters: component.config.characters.map(character => ({
                ...character, tts_voice_settings: { "plugin:voice-plugin:tts": { voice: "sample" } },
            })),
        });
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector(".crew-voice").textContent).toBe("Sample Voice");
    });

    it("prevents adding a fourth active character and disables Add to Crew", async () => {
        fixture.componentRef.setInput("config", {
            ...component.config,
            characters: [...component.config.characters, { name: "Fourth" }],
            active_characters: [0, 1, 2],
        });
        component.toggleRosterManager();
        fixture.detectChanges();
        expect(component.crewIsFull).toBeTrue();
        expect(fixture.nativeElement.querySelector("#standby-roster .crew-add-action").disabled).toBeTrue();
        await component.setCrewMember(3, true);
        expect(configService.changeConfig).not.toHaveBeenCalled();

        fixture.componentRef.setInput("config", { ...component.config, active_characters: [0, 1] });
        fixture.detectChanges();
        expect(fixture.nativeElement.querySelector("#standby-roster .crew-add-action").disabled).toBeFalse();
        await component.setCrewMember(3, true);
        expect(configService.changeConfig).toHaveBeenCalledOnceWith({ active_characters: [0, 1, 3] });
    });

    it("does not remove the primary or save invalid indices", async () => {
        await component.setCrewMember(0, false);
        await component.setCrewMember(99, true);
        expect(configService.changeConfig).not.toHaveBeenCalled();
    });

    it("selects a primary through the existing character-selection flow", () => {
        const selected = spyOn(component.primarySelected, "emit");
        fixture.nativeElement.querySelectorAll("button.crew-portrait")[1].click();
        expect(selected).toHaveBeenCalledOnceWith(1);
        expect(configService.changeConfig).not.toHaveBeenCalled();
    });

    it("previews a hovered character without selecting or saving it", () => {
        const preview = spyOn(component.characterPreviewed, "emit");
        const selected = spyOn(component.primarySelected, "emit");
        const portrait = fixture.nativeElement.querySelectorAll("button.crew-portrait")[1];
        portrait.parentElement.dispatchEvent(new MouseEvent("mouseenter"));
        expect(preview).toHaveBeenCalledWith(1);
        portrait.parentElement.dispatchEvent(new MouseEvent("mouseleave"));
        expect(preview).toHaveBeenCalledWith(null);
        expect(selected).not.toHaveBeenCalled();
        expect(configService.changeConfig).not.toHaveBeenCalled();
    });

    it("hides management and prevents mutations in preview-only mode", async () => {
        fixture.componentRef.setInput("previewOnly", true);
        component.showManager = true;
        fixture.detectChanges();
        const selected = spyOn(component.primarySelected, "emit");
        fixture.nativeElement.querySelectorAll("button.crew-portrait")[1].click();
        await component.setCrewMember(2, true);
        expect(selected).not.toHaveBeenCalled();
        expect(configService.changeConfig).not.toHaveBeenCalled();
        expect(fixture.nativeElement.querySelector(".crew-header")).toBeNull();
        expect(fixture.nativeElement.querySelector("#standby-roster")).toBeNull();
        expect(fixture.nativeElement.querySelector(".crew-membership-button")).toBeNull();
        expect(fixture.nativeElement.querySelector(".crew-standby-action")).toBeNull();
        expect(fixture.nativeElement.querySelector(".crew-add-action")).toBeNull();
        expect(fixture.nativeElement.querySelector(".crew-edit-button")).toBeNull();
    });

    it("keeps the focused preview after the mouse leaves", () => {
        const preview = spyOn(component.characterPreviewed, "emit");
        const portrait = fixture.nativeElement.querySelectorAll("button.crew-portrait")[1];
        portrait.dispatchEvent(new FocusEvent("focus"));
        portrait.parentElement.dispatchEvent(new MouseEvent("mouseenter"));
        portrait.parentElement.dispatchEvent(new MouseEvent("mouseleave"));
        expect(preview.calls.mostRecent().args).toEqual([1]);
        portrait.dispatchEvent(new FocusEvent("blur"));
        expect(preview.calls.mostRecent().args).toEqual([null]);
    });

    for (const active of [[], [0]]) {
        it(`hides overview roster portraits with ${active.length} active entries but keeps management available`, () => {
            fixture.componentRef.setInput("config", { ...component.config, active_characters: active });
            fixture.detectChanges();
            expect(fixture.nativeElement.querySelectorAll("button.crew-portrait").length).toBe(0);
            fixture.nativeElement.querySelector(".crew-header button").click();
            fixture.detectChanges();
            expect(fixture.nativeElement.querySelector("#standby-roster")).not.toBeNull();
            const preview = spyOn(component.characterPreviewed, "emit");
            component.setHoveredCharacter(0);
            expect(preview).toHaveBeenCalledOnceWith(null);
        });
    }

    it("falls back to the primary for older configurations", () => {
        fixture.componentRef.setInput("config", {
            ...component.config, active_characters: undefined,
        });
        fixture.detectChanges();
        expect(component.activeIndices).toEqual([0]);
    });

    it("reports a failed save without changing the displayed roster", async () => {
        configService.changeConfig.and.rejectWith(new Error("offline"));
        spyOn(console, "error");
        await component.setCrewMember(2, true);
        expect(component.activeIndices).toEqual([0, 1]);
        expect(component.saving).toBeFalse();
        expect(snackBar.open).toHaveBeenCalled();
    });

    it("loads each avatar once and cleans up object URLs", async () => {
        avatarService.getAvatarWithMime.and.resolveTo({ url: "blob:crew-avatar", mimeType: "image/png" });
        fixture.componentRef.setInput("config", {
            ...component.config,
            characters: component.config.characters.map((character) => ({ ...character, avatar: "crew.png" })),
        });
        fixture.detectChanges();
        await fixture.whenStable();
        expect(avatarService.getAvatarWithMime).toHaveBeenCalledOnceWith("crew.png");
        expect(component.usesSpriteSheet(component.config.characters[0])).toBeTrue();
        const revoke = spyOn(URL, "revokeObjectURL");
        fixture.destroy();
        expect(revoke).toHaveBeenCalledOnceWith("blob:crew-avatar");
    });
});
