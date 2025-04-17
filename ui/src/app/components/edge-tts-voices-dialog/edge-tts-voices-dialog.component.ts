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
  templateUrl: './edge-tts-voices-dialog.component.html',
  styles: [`
    .voice-selector-container {
      display: flex;
      height: 350px;
      margin-top: 10px;
      gap: 16px;
      border: 1px solid rgba(0, 0, 0, 0.12);
      border-radius: 4px;
    }
    
    .language-list {
      flex: 0 0 30%;
      border-right: 1px solid rgba(0, 0, 0, 0.12);
      overflow-y: auto;
    }
    
    .language-selection-list {
      height: 100%;
    }
    
    .voice-list {
      flex: 0 0 70%;
      overflow-y: auto;
    }
    
    .select-language-prompt {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100%;
      color: rgba(0, 0, 0, 0.54);
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
  selectedLocale: string | null = null;
  locales: string[] = [];
  
  constructor(
    public dialogRef: MatDialogRef<EdgeTtsVoicesDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: EdgeTtsVoiceData
  ) {
    this.selectedVoice = data.selectedVoice;
  }
  
  ngOnInit(): void {
    this.groupVoicesByLocale();
    // Set initial locale based on selected voice
    if (this.selectedVoice) {
      const voiceObj = this.data.voices.find(v => v.value === this.selectedVoice);
      if (voiceObj) {
        this.selectedLocale = voiceObj.locale;
      }
    }
    
    // If no locale is selected, select the first one
    if (!this.selectedLocale && this.locales.length > 0) {
      this.selectedLocale = this.locales[0];
    }
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
  
  onSelectLocale(locale: string): void {
    this.selectedLocale = locale;
  }
  
  onCancel(): void {
    this.dialogRef.close();
  }
  
  onSelect(voice: string): void {
    this.dialogRef.close(voice);
  }
} 