export function audioDeviceAvailable(selection: string | null | undefined, devices?: string[]): boolean {
    const identifier = selection == null || selection === "" || selection === "pulse" ? "default" : selection;
    return devices?.includes(identifier) ?? false;
}

export function audioDeviceLabel(selection: string | null | undefined, labels?: Record<string, string>): string {
    const identifier = selection == null || selection === "" || selection === "pulse" ? "default" : selection;
    return labels?.[identifier] ?? (identifier === "default" ? "System default" : "Unavailable device");
}
