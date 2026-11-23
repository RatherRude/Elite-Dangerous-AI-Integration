import { TestBed } from '@angular/core/testing';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { SettingsHeaderLinkComponent } from './settings-header-link.component';

describe('settings header links', () => {
  beforeEach(() => TestBed.configureTestingModule({
    imports: [SettingsHeaderLinkComponent, TranslateModule.forRoot()],
  }));

  it('translates both parts and opens an external link without replacing the application', () => {
    const translate = TestBed.inject(TranslateService);
    translate.setTranslation('en', {plugin: {example: {prompt: 'Enjoy this plugin?', link: 'Support development'}}});
    translate.setTranslation('fr', {plugin: {example: {prompt: 'Ce plugin vous plaît ?', link: 'Soutenez son développement'}}});
    translate.use('en');
    const fixture = TestBed.createComponent(SettingsHeaderLinkComponent);
    fixture.componentRef.setInput('link', {text: 'plugin.example.prompt', label: 'plugin.example.link', url: 'https://example.org/support'});
    fixture.detectChanges();
    const anchor = fixture.nativeElement.querySelector('a') as HTMLAnchorElement;
    expect(fixture.nativeElement.textContent).toContain('Enjoy this plugin?');
    expect(anchor.href).toBe('https://example.org/support');
    expect(anchor.target).toBe('_blank');
    expect(anchor.rel).toContain('noopener');
    translate.use('fr');
    fixture.detectChanges();
    expect(anchor.textContent).toContain('Soutenez son développement');
    expect(fixture.nativeElement.textContent).toContain('Ce plugin vous plaît ?');
  });

  it('renders nothing for legacy plugins or non-web URLs', () => {
    const fixture = TestBed.createComponent(SettingsHeaderLinkComponent);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('a')).toBeNull();
    for (const url of ['javascript:alert(1)', 'file:///secret', 'invalid']) {
      fixture.componentRef.setInput('link', {text: 'Prompt', label: 'Link', url});
      fixture.detectChanges();
      expect(fixture.nativeElement.querySelector('a')).toBeNull();
    }
  });
});
