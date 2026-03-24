import { APP_INITIALIZER, ApplicationConfig } from "@angular/core";
import { provideRouter, withHashLocation } from "@angular/router";

import { routes } from "./app.routes";
import { provideAnimationsAsync } from "@angular/platform-browser/animations/async";
import { provideHttpClient } from "@angular/common/http";
import { MAT_DIALOG_DEFAULT_OPTIONS, MatDialogModule } from "@angular/material/dialog";
import { importProvidersFrom } from "@angular/core";
import { MarkdownModule } from 'ngx-markdown';
import { AvatarMigrationService } from "./services/avatar-migration.service";

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes, withHashLocation()),
    provideAnimationsAsync(),
    provideHttpClient(),
    importProvidersFrom(MatDialogModule),
    importProvidersFrom(MarkdownModule.forRoot()),
    {
      provide: APP_INITIALIZER,
      multi: true,
      deps: [AvatarMigrationService],
      useFactory: (avatarMigrationService: AvatarMigrationService) => () => {
        avatarMigrationService.init();
      },
    },
    { provide: MAT_DIALOG_DEFAULT_OPTIONS, useValue: { hasBackdrop: true, autoFocus: true } }
  ],
};
