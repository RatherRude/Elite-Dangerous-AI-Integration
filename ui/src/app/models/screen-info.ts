export interface ScreenInfo {
    id: number;
    label: string;
    bounds: { x: number; y: number; width: number; height: number };
    primary: boolean;
} 