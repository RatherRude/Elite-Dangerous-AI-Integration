import { Injectable } from "@angular/core";
import { BehaviorSubject } from "rxjs";

export const FONT_SCALE_STORAGE_KEY = "covas.ui.font-scale";
export const FONT_SCALE_DEFAULT = 1;
export const FONT_SCALE_MIN = 0.875;
export const FONT_SCALE_MAX = 1.5;

@Injectable({ providedIn: "root" })
export class FontScaleService {
  private readonly scaleSubject = new BehaviorSubject<number>(FONT_SCALE_DEFAULT);
  readonly scale$ = this.scaleSubject.asObservable();

  get scale(): number {
    return this.scaleSubject.value;
  }

  init(): void {
    this.applyScale(this.readStoredScale());
    window.addEventListener("storage", this.onStorage);
  }

  setScale(scale: number): void {
    const normalizedScale = this.normalizeScale(scale);
    localStorage.setItem(FONT_SCALE_STORAGE_KEY, String(normalizedScale));
    this.applyScale(normalizedScale);
  }

  reset(): void {
    this.setScale(FONT_SCALE_DEFAULT);
  }

  private readonly onStorage = (event: StorageEvent): void => {
    if (event.key === FONT_SCALE_STORAGE_KEY) {
      this.applyScale(this.normalizeScale(Number(event.newValue)));
    }
  };

  private readStoredScale(): number {
    return this.normalizeScale(Number(localStorage.getItem(FONT_SCALE_STORAGE_KEY)));
  }

  private normalizeScale(scale: number): number {
    if (!Number.isFinite(scale) || scale < FONT_SCALE_MIN || scale > FONT_SCALE_MAX) {
      return FONT_SCALE_DEFAULT;
    }
    return scale;
  }

  private applyScale(scale: number): void {
    const root = document.documentElement;
    root.style.fontSize = `${scale * 100}%`;
    root.style.setProperty("--ui-font-scale", String(scale));
    this.scaleSubject.next(scale);
    window.dispatchEvent(new CustomEvent("covas-font-scale-change", { detail: scale }));
  }
}
