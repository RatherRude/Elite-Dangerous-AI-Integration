import { Component, Input, inject } from '@angular/core';
import { TranslateService } from '@ngx-translate/core';
import { SettingsHeaderLink } from '../../services/plugin-settings';
import { resolveSettingText } from '../../services/setting-text';

@Component({
  selector: 'app-settings-header-link',
  standalone: true,
  template: `
    @if (link && validUrl(link.url)) {
      <span>{{ resolve(link.text) }}</span>
      <a [href]="link.url" target="_blank" rel="noopener noreferrer">{{ resolve(link.label) }} ↗</a>
    }
  `,
  styles: [`
    :host { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .25rem;
      margin: .5rem 0; font-size: .8rem; line-height: 1.5; color: var(--mat-app-text-color, inherit); }
    span { opacity: .7; }
    a { color: inherit; text-underline-offset: .2em; }
    a:hover, a:focus-visible { text-decoration-thickness: 2px; }
  `],
})
export class SettingsHeaderLinkComponent {
  @Input() link?: SettingsHeaderLink;
  private readonly translate = inject(TranslateService);

  resolve(value: string): string {
    return resolveSettingText(this.translate, value);
  }

  validUrl(value: string): boolean {
    try {
      return ['https:', 'http:'].includes(new URL(value).protocol);
    } catch {
      return false;
    }
  }

}
