import { Component, Inject, OnInit } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDividerModule } from '@angular/material/divider';
import { MatTabsModule } from '@angular/material/tabs';
import { MatListModule } from '@angular/material/list';

export interface EdgeTtsVoiceData {
  voices: { value: string; label: string; locale: string; }[];
  selectedVoice: string;
}

@Component({
  selector: 'app-edge-tts-voices-dialog',
  template: `
    <h2 mat-dialog-title>Select Voice</h2>

    <div mat-dialog-content>
      <mat-form-field appearance="outline" style="width: 100%; margin-bottom: 16px;">
        <mat-label>Search Voices</mat-label>
        <input matInput [(ngModel)]="searchQuery" placeholder="Search by name, locale, or voice ID">
      </mat-form-field>

      <div *ngIf="getFilteredLocales().length === 0" class="no-results">
        <p>No voices found matching "{{ searchQuery }}"</p>
      </div>

      <mat-tab-group *ngIf="getFilteredLocales().length > 0">
        <mat-tab *ngFor="let locale of getFilteredLocales()" [label]="locale">
          <div class="voice-list">
            <mat-selection-list [multiple]="false">
              <mat-list-option *ngFor="let voice of filterVoices()[locale]" 
                              [value]="voice.value"
                              [selected]="voice.value === selectedVoice"
                              (click)="onSelect(voice.value)">
                <div class="voice-item">
                  <span class="voice-name">{{ voice.label }}</span>
                  <span class="voice-id">{{ voice.value }}</span>
                </div>
              </mat-list-option>
            </mat-selection-list>
          </div>
        </mat-tab>
      </mat-tab-group>
    </div>

    <div mat-dialog-actions align="end">
      <button mat-button (click)="onCancel()">Cancel</button>
    </div>
  `,
  styles: [`
    .voice-list {
      height: 300px;
      overflow-y: auto;
      margin-top: 10px;
    }
    
    .voice-item {
      display: flex;
      flex-direction: column;
    }
    
    .voice-name {
      font-weight: 500;
    }
    
    .voice-id {
      font-size: 0.8em;
      color: #666;
    }
    
    .no-results {
      text-align: center;
      padding: 20px;
      color: #666;
    }
    
    ::ng-deep .mat-mdc-dialog-content {
      max-height: 80vh;
    }
    
    ::ng-deep .mat-mdc-tab-body-wrapper {
      min-height: 350px;
    }
  `],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatDialogModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDividerModule,
    MatTabsModule,
    MatListModule
  ]
})
export class EdgeTtsVoicesDialogComponent implements OnInit {
  searchQuery: string = '';
  groupedVoices: { [locale: string]: { value: string; label: string; locale: string; }[] } = {};
  selectedVoice: string = '';
  locales: string[] = [];
  
  constructor(
    public dialogRef: MatDialogRef<EdgeTtsVoicesDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: EdgeTtsVoiceData
  ) {
    this.selectedVoice = data.selectedVoice;
  }
  
  ngOnInit(): void {
    this.groupVoicesByLocale();
  }
  
  groupVoicesByLocale(): void {
    this.groupedVoices = {};
    this.data.voices.forEach(voice => {
      if (!this.groupedVoices[voice.locale]) {
        this.groupedVoices[voice.locale] = [];
      }
      this.groupedVoices[voice.locale].push(voice);
    });
    
    // Sort locales alphabetically
    this.locales = Object.keys(this.groupedVoices).sort();
  }
  
  filterVoices(): { [locale: string]: { value: string; label: string; locale: string; }[] } {
    if (!this.searchQuery.trim()) {
      return this.groupedVoices;
    }
    
    const query = this.searchQuery.toLowerCase();
    const result: { [locale: string]: { value: string; label: string; locale: string; }[] } = {};
    
    Object.keys(this.groupedVoices).forEach(locale => {
      const filteredVoices = this.groupedVoices[locale].filter(voice => 
        voice.label.toLowerCase().includes(query) || 
        voice.value.toLowerCase().includes(query) ||
        locale.toLowerCase().includes(query)
      );
      
      if (filteredVoices.length > 0) {
        result[locale] = filteredVoices;
      }
    });
    
    return result;
  }
  
  getFilteredLocales(): string[] {
    const filteredGroups = this.filterVoices();
    return Object.keys(filteredGroups).sort();
  }
  
  onCancel(): void {
    this.dialogRef.close();
  }
  
  onSelect(voice: string): void {
    this.dialogRef.close(voice);
  }
} 