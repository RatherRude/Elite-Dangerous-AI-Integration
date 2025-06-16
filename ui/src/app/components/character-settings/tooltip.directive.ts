     import {
       Directive,
       ElementRef,
       Input,
       HostListener,
       Renderer2,
       OnDestroy
     } from '@angular/core';

     @Directive({
       selector: '[appTooltip]',
       standalone: true
     })

     export class TooltipDirective implements OnDestroy {
       @Input('appTooltip') tooltipText = '';
       @Input() tooltipPosition: 'top' | 'bottom' | 'left' | 'right' = 'top';

       private tooltip: HTMLElement | null = null;

       constructor(private el: ElementRef, private renderer: Renderer2) {}

       @HostListener('mouseenter')
       onMouseEnter() {
         if (!this.tooltip) {
           this.showTooltip();
         }
       }

       @HostListener('mouseleave')
       onMouseLeave() {
         this.removeTooltip();
       }

       showTooltip() {
         this.tooltip = this.renderer.createElement('div');
         const tooltip = this.tooltip!; // Non-null assertion

         tooltip.innerText = this.tooltipText;

         this.renderer.addClass(tooltip, 'custom-tooltip');
         this.renderer.addClass(tooltip, `tooltip-${this.tooltipPosition}`);

         document.body.appendChild(tooltip);

         const hostPos = this.el.nativeElement.getBoundingClientRect();
         const tooltipPos = tooltip.getBoundingClientRect();

         const scrollY = window.scrollY || document.documentElement.scrollTop;
         const scrollX = window.scrollX || document.documentElement.scrollLeft;

         let top = 0, left = 0;

         switch (this.tooltipPosition) {
           case 'top':
             top = hostPos.top - tooltipPos.height - 8;
             left = hostPos.left + (hostPos.width - tooltipPos.width) / 2;
             break;
           case 'bottom':
             top = hostPos.bottom + 8;
             left = hostPos.left + (hostPos.width - tooltipPos.width) / 2;
             break;
           case 'left':
             top = hostPos.top + (hostPos.height - tooltipPos.height) / 2;
             left = hostPos.left - tooltipPos.width - 8;
             break;
           case 'right':
             top = hostPos.top + (hostPos.height - tooltipPos.height) / 2;
             left = hostPos.right + 8;
             break;
         }

         tooltip.style.position = 'absolute';
         tooltip.style.top = `${top + scrollY}px`;
         tooltip.style.left = `${left + scrollX}px`;
       }


       removeTooltip() {
         if (this.tooltip && this.tooltip.parentNode) {
           this.tooltip.parentNode.removeChild(this.tooltip);
           this.tooltip = null;
         }
       }

       ngOnDestroy(): void {
         this.removeTooltip();
       }
     }
