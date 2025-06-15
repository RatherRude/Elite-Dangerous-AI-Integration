import { Component, EventEmitter, Input, Output } from "@angular/core";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatIconModule } from "@angular/material/icon";
import {
  SubmitInputMessage,
  TauriService,
} from "../../services/tauri.service.js";

@Component({
  selector: "app-input-container",
  standalone: true,
  imports: [MatFormFieldModule, MatInputModule, MatIconModule],
  templateUrl: "./input-container.component.html",
  styleUrl: "./input-container.component.css",
})
export class InputContainerComponent {
  constructor(private tauri: TauriService) {}

  value: string = "";

  onKeyDown(event: Event) {
    const input = event.target as HTMLInputElement;
    this.value = input.value;
    // emit the value to the parent when pressing enter and clear the input
    if (event instanceof KeyboardEvent && event.key === "Enter") {
      this.tauri.send_command(
        { type: "submit_input", input: input.value } as SubmitInputMessage,
      );
      input.value = "";
      this.value = "";
    }
  }
}
