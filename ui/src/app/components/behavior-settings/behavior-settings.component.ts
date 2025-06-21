import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatSlideToggle } from "@angular/material/slide-toggle";
import { Config, ConfigService } from "../../services/config.service.js";
import { Subscription } from "rxjs";
import { MatSnackBar } from "@angular/material/snack-bar";
import { FormsModule } from "@angular/forms";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";

@Component({
    selector: "app-behavior-settings",
    standalone: true,
    imports: [
        CommonModule,
        MatInputModule,
        MatFormFieldModule,
        FormsModule,
        MatButtonModule,
        MatSlideToggle,
    ],
    templateUrl: "./behavior-settings.component.html",
    styleUrl: "./behavior-settings.component.css",
})
export class BehaviorSettingsComponent {
    config: Config | null = null;
    configSubscription: Subscription;
    constructor(
        private configService: ConfigService,
        private snackBar: MatSnackBar,
    ) {
        this.configSubscription = this.configService.config$.subscribe(
            (config) => {
                this.config = config;
            },
        );
    }
    ngOnDestroy() {
        // Unsubscribe from the config observable to prevent memory leaks
        if (this.configSubscription) {
            this.configSubscription.unsubscribe();
        }
    }

    async onConfigChange(partialConfig: Partial<Config>) {
        if (this.config) {
            console.log("Sending config update to backend:", partialConfig);

            try {
                await this.configService.changeConfig(partialConfig);
            } catch (error) {
                console.error("Error updating config:", error);
                this.snackBar.open("Error updating configuration", "OK", {
                    duration: 5000,
                });
            }
        }
    }
}
