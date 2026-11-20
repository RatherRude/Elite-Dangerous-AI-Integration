import { audioDeviceAvailable, audioDeviceLabel } from "./audio-devices";
import { Config } from "./config.service";
import { GeneralSettingsComponent } from "../components/general-settings/general-settings.component";
import { AdvancedSettingsComponent } from "../components/advanced-settings/advanced-settings.component";

describe("audio device migration", () => {
    const devices = ["default", "sink-usb", "sink-other"];
    const labels = { default: "System default", "sink-usb": "USB", "sink-other": "USB" };

    it("checks exact IDs rather than old names, substrings, or devices on another machine", () => {
        expect(audioDeviceAvailable("sink-usb", devices)).toBeTrue();
        for (const selection of ["USB", "sink", "removed-endpoint", "source-usb"]) {
            expect(audioDeviceAvailable(selection, devices)).toBeFalse();
        }
    });

    it("recognizes default aliases without claiming readiness before enumeration", () => {
        for (const selection of [undefined, null, "", "pulse", "default"]) {
            expect(audioDeviceAvailable(selection, devices)).toBeTrue();
            expect(audioDeviceAvailable(selection, undefined)).toBeFalse();
            expect(audioDeviceLabel(selection, labels)).toBe("System default");
        }
    });

    it("shows names without adding IDs and does not expose unavailable IDs", () => {
        expect(audioDeviceLabel("sink-usb", labels)).toBe("USB");
        expect(audioDeviceLabel("sink-other", labels)).toBe("USB");
        expect(audioDeviceLabel("endpoint-uuid", labels)).toBe("Unavailable device");
    });

    for (const componentType of [GeneralSettingsComponent, AdvancedSettingsComponent]) {
        it(`${componentType.name} checks input and output independently and after refresh`, () => {
            const component = Object.create(componentType.prototype) as GeneralSettingsComponent | AdvancedSettingsComponent;
            component.config = {
                input_device_name: "old microphone name", output_device_name: "sink-usb",
                stt_provider: "openai", tts_provider: "openai",
            } as Config;
            component.system = {
                input_device_names: ["default", "source-usb"], output_device_names: devices,
            } as NonNullable<typeof component.system>;
            expect(component.inputDeviceAvailable).toBeFalse();
            expect(component.outputDeviceAvailable).toBeTrue();
            component.config.input_device_name = "source-usb";
            expect(component.inputDeviceAvailable).toBeTrue();
            component.system.input_device_names = ["default"];
            expect(component.inputDeviceAvailable).toBeFalse();
        });
    }

    it("marks preflight unready for unavailable selections without overwriting them", () => {
        const component = Object.create(GeneralSettingsComponent.prototype) as GeneralSettingsComponent;
        component.config = {
            input_device_name: "old microphone name", output_device_name: "sink-usb",
            stt_provider: "openai", tts_provider: "openai",
        } as Config;
        component.system = {
            input_device_names: ["default", "source-usb"], output_device_names: devices,
        } as NonNullable<typeof component.system>;
        expect(component.soundInputReady).toBeFalse();
        expect(component.soundOutputReady).toBeTrue();
        expect(component.config.input_device_name).toBe("old microphone name");
    });
});
