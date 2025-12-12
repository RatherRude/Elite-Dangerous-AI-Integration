import { Injectable } from "@angular/core";
import { BehaviorSubject } from "rxjs";
import { BaseMessage, TauriService } from "./tauri.service";

/**
 * Message interface for GenUI code updates from backend
 */
interface GenUIMessage extends BaseMessage {
    type: "genui";
    code: string;
}

/**
 * Message interface for state updates from backend
 */
interface StatesMessage extends BaseMessage {
    type: "states";
    states: Record<string, any>;
}

/**
 * GenUiService - Manages the LLM-generated UI code and game state
 * 
 * This service provides:
 * - uiCode$: Observable of the current Preact component code (changes rarely)
 * - uiState$: Observable of the current game state (changes frequently)
 * 
 * Connected to Python backend via TauriService.
 */
@Injectable({
    providedIn: "root",
})
export class GenUiService {
    // The LLM-generated Preact component code
    private uiCodeSubject = new BehaviorSubject<string | null>(null);
    public uiCode$ = this.uiCodeSubject.asObservable();

    // The current game state to pass to the component
    private uiStateSubject = new BehaviorSubject<any>(null);
    public uiState$ = this.uiStateSubject.asObservable();

    constructor(private tauriService: TauriService) {
        this.subscribeToBackend();
    }

    /**
     * Subscribe to backend messages for GenUI code and state updates
     */
    private subscribeToBackend() {
        this.tauriService.output$.subscribe((message) => {
            if (message.type === 'genui') {
                const genUIMessage = message as GenUIMessage;
                this.setUiCode(genUIMessage.code);
            } else if (message.type === 'states') {
                const statesMessage = message as StatesMessage;
                // Transform projected states to the format expected by UI components
                const state = this.transformState(statesMessage.states);
                this.setUiState(state);
            }
        });
    }

    /**
     * Transform projected states from backend to UI-friendly format
     */
    private transformState(projectedStates: Record<string, any>): any {
        const state: any = {
            ...this.getCurrentState(),
            ...projectedStates,
        };
        
        return state;
    }

    /**
     * Update the UI code (called when LLM generates new code)
     */
    public setUiCode(code: string) {
        this.uiCodeSubject.next(code);
    }

    /**
     * Update the game state (called frequently from game events)
     */
    public setUiState(state: any) {
        this.uiStateSubject.next(state);
    }

    /**
     * Get the current UI code
     */
    public getCurrentCode(): string | null {
        return this.uiCodeSubject.value;
    }

    /**
     * Get the current state
     */
    public getCurrentState(): any {
        return this.uiStateSubject.value;
    }
}
