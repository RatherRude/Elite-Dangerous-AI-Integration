import { Component, Input } from "@angular/core";

@Component({
    selector: "app-config-tab-shell",
    standalone: true,
    templateUrl: "./config-tab-shell.component.html",
    styleUrl: "./config-tab-shell.component.scss",
})
export class ConfigTabShellComponent {
    @Input() eyebrow = "Configuration";
    @Input({ required: true }) title = "";
    @Input() description = "";
}
