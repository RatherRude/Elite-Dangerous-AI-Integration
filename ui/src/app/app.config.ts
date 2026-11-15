import { APP_INITIALIZER, ApplicationConfig } from "@angular/core";
import { provideRouter, withHashLocation } from "@angular/router";

import { routes } from "./app.routes";
import { provideAnimationsAsync } from "@angular/platform-browser/animations/async";
import { provideHttpClient } from "@angular/common/http";
import { TranslateLoader, TranslateService, provideTranslateService } from "@ngx-translate/core";
import { InlineTranslateLoader } from "./services/inline-translate-loader";
import { firstValueFrom } from "rxjs";
import { MAT_DIALOG_DEFAULT_OPTIONS, MatDialogModule } from "@angular/material/dialog";
import { MatSnackBarModule } from "@angular/material/snack-bar";
import { importProvidersFrom } from "@angular/core";
import { MarkdownModule } from 'ngx-markdown';
import { AvatarMigrationService } from "./services/avatar-migration.service";
import { FontScaleService } from "./services/font-scale.service";

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes, withHashLocation()),
    provideAnimationsAsync(),
    provideHttpClient(),
    provideTranslateService({
      loader: {
        provide: TranslateLoader,
        useFactory: () => new InlineTranslateLoader(),
      },
      defaultLanguage: "en",
    }),
    {
      provide: APP_INITIALIZER,
      multi: true,
      deps: [TranslateService],
      useFactory: (translate: TranslateService) => () => firstValueFrom(translate.use("en")),
    },
    importProvidersFrom(MatDialogModule),
    importProvidersFrom(MatSnackBarModule),
    importProvidersFrom(MarkdownModule.forRoot()),
    {
      provide: APP_INITIALIZER,
      multi: true,
      deps: [AvatarMigrationService],
      useFactory: (avatarMigrationService: AvatarMigrationService) => () => {
        avatarMigrationService.init();
      },
    },
    {
      provide: APP_INITIALIZER,
      multi: true,
      deps: [FontScaleService],
      useFactory: (fontScaleService: FontScaleService) => () => {
        fontScaleService.init();
      },
    },
    { provide: MAT_DIALOG_DEFAULT_OPTIONS, useValue: { hasBackdrop: true, autoFocus: true } }
  ],
};
