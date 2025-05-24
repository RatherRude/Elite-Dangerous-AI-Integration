import { Component, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { LoggingService, LogMessage } from '../../services/logging.service';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-covas-log',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './covas-log.component.html',
  styleUrl: './covas-log.component.css'
})
export class CovasLogComponent implements OnDestroy {
  latestCovasLog: LogMessage | null = null;
  private subscription: Subscription;

  constructor(private loggingService: LoggingService) {
    // Subscribe to log updates and filter for the latest covas log
    this.subscription = this.loggingService.logs$.subscribe((logs) => {
      // Filter for covas logs and get the latest one
      const covasLogs = logs.filter(log => log.prefix === 'covas');
      if (covasLogs.length > 0) {
        this.latestCovasLog = covasLogs[covasLogs.length - 1];
      }
    });
  }

  ngOnDestroy() {
    if (this.subscription) {
      this.subscription.unsubscribe();
    }
  }

  getLogColor(prefix: string): string {
    return '#2196F3'; // Blue color for covas
  }
} 