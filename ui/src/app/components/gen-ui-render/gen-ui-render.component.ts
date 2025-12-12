import { 
  Component, 
  ElementRef, 
  ViewChild, 
  AfterViewInit, 
  OnDestroy, 
  NgZone 
} from '@angular/core';
import { Subscription } from 'rxjs';
import { CommonModule } from '@angular/common';
import { GenUiService } from '../../services/gen-ui.service';

@Component({
  selector: 'app-gen-ui-render',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div style="width: 100%; height: 100%; position: relative;">
      <iframe 
        #sandbox 
        style="width: 100%; height: 100%; border: none; background: transparent;"
        sandbox="allow-scripts allow-same-origin"
      ></iframe>
    </div>
  `,
  styles: [`
    :host { 
      display: block; 
      height: 100%; 
      width: 100%; 
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
    }
  `]
})
export class GenUiRenderComponent implements AfterViewInit, OnDestroy {
  @ViewChild('sandbox') iframeRef!: ElementRef<HTMLIFrameElement>;
  
  private codeSub: Subscription | null = null;
  private stateSub: Subscription | null = null;

  constructor(
    private genUiService: GenUiService,
    private ngZone: NgZone
  ) {}

  ngAfterViewInit() {
    // 1. Subscribe to CODE changes (Rare)
    this.codeSub = this.genUiService.uiCode$.subscribe((code) => {
      if (code) this.rebuildSandbox(code);
    });

    // 2. Subscribe to STATE changes (Frequent)
    // We run this outside Angular to prevent triggering Change Detection 
    // on the main thread frequently.
    this.ngZone.runOutsideAngular(() => {
      this.stateSub = this.genUiService.uiState$.subscribe((state) => {
        if (state) this.updateSandboxState(state);
      });
    });
  }

  ngOnDestroy() {
    this.codeSub?.unsubscribe();
    this.stateSub?.unsubscribe();
  }

  /**
   * REBUILD SANDBOX
   * Destroys the current iframe document and writes a fresh one 
   * with the new code and Preact libraries.
   */
  private rebuildSandbox(llmCode: string) {
    const iframe = this.iframeRef.nativeElement;
    const doc = iframe.contentDocument || iframe.contentWindow?.document;

    if (!doc) return;

    // The HTML Boilerplate for the Sandbox
    // Note: We use ES Modules (type="module") to load Preact from CDN.
    const htmlContent = `
      <!DOCTYPE html>
      <html style="background: transparent; color-scheme: only dark;">
      <head>
        <meta charset="UTF-8">
        <meta name="color-scheme" content="only dark">
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
          :root { color-scheme: only dark; }
          html, body { background: transparent !important; overflow: hidden; margin: 0; padding: 0; color-scheme: only dark; }
          /* Scrollbar hiding for cleaner UI */
          ::-webkit-scrollbar { display: none; }
        </style>
      </head>
      <body>
        <div id="app-root"></div>

        <script type="module">
          import { h, render } from 'https://esm.sh/preact@10.19.3';
          import htm from 'https://esm.sh/htm@3.1.1';
          
          // Bind HTM to Preact
          const html = htm.bind(h);
          
          // Globalize for the LLM script to use
          window.html = html;
          window.preactRender = render;
          window.h = h;

          // Declare App in global scope
          window.App = null;
          
          // Signal that runtime is ready
          window.isRuntimeReady = true;

          // Load the LLM code
          try {
            ${llmCode}
            // Capture App component
            window.App = App;
            console.log("GenUI: App component loaded");
          } catch(e) {
            console.error("GenUI: Error loading component", e);
            document.body.innerHTML = '<div class="text-red-500 p-4">Runtime Error: ' + e.message + '</div>';
          }
        </script>

        <script>
          // This function is called by Angular to update state
          window.updateState = (newState) => {
            if (!window.App || !window.preactRender || !window.html) {
              console.warn("GenUI: Runtime not ready");
              return;
            }
            
            const root = document.getElementById('app-root');
            
            // Preact Diffing Magic happens here
            // We render <App state={newState} />
            try {
              window.preactRender(
                window.html\`<\${window.App} state=\${newState} />\`, 
                root
              );
            } catch(e) {
              console.error("GenUI: Render error", e);
            }
          };
        </script>
      </body>
      </html>
    `;

    // Write to the iframe (synchronous reset)
    doc.open();
    doc.write(htmlContent);
    doc.close();
  }

  /**
   * UPDATE STATE
   * Pushes data into the iframe context.
   */
  private updateSandboxState(state: any) {
    const win = this.iframeRef.nativeElement.contentWindow as any;
    
    // Check if the iframe has finished loading and defined our update hook
    if (win && typeof win.updateState === 'function') {
      win.updateState(state);
    }
  }
}
