import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatCardModule } from "@angular/material/card";
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatNativeDateModule } from '@angular/material/core';
import { EventService, MemoryEvent } from "../../services/event.service";
import { TauriService, QueryMemoriesMessage, GetMemoriesByDateMessage, GetAvailableDatesMessage } from "../../services/tauri.service";
import { Subscription } from "rxjs";

interface MemorySearchResult {
  score: number;
  summary: string;
  inserted_at?: string;
}

interface MemoryEntry {
  id: number;
  content: string;
  inserted_at: string;
  metadata: Record<string, any>;
}

interface DateInfo {
  date: string;
  count: number;
}

@Component({
  selector: "app-memories-container",
  standalone: true,
  imports: [
    CommonModule, 
    MatCardModule, 
    FormsModule,
    MatDatepickerModule,
    MatInputModule,
    MatFormFieldModule,
    MatNativeDateModule
  ],
  templateUrl: "./memories-container.component.html",
  styleUrls: ["./memories-container.component.css"],
})
export class MemoriesContainerComponent implements OnInit, OnDestroy {
  private sub?: Subscription;
  private outputSub?: Subscription;
  public memories: { timestamp: string; content: string }[] = [];
  public selectedDate: Date = new Date();
  public logbookQuestion: string = '';
  public searchResults: MemorySearchResult[] = [];
  public showSearchResults: boolean = false;
  public isSearching: boolean = false;
  public hasPerformedSearch: boolean = false;
  public loadedEntries: MemoryEntry[] = [];
  public isLoadingEntries: boolean = false;
  public displayedEntries: { timestamp: string; content: string }[] = [];
  public availableDates: DateInfo[] = [];
  private availableDatesSet: Set<string> = new Set();

  constructor(
    private events: EventService,
    private tauri: TauriService
  ) {}

  ngOnInit(): void {
    this.sub = this.events.events$.subscribe((all) => {
      const mems = all
        .map((m) => m.event)
        .filter((e): e is MemoryEvent => (e as any)?.kind === "memory")
        .map((e) => ({ timestamp: (e as MemoryEvent).timestamp, content: (e as MemoryEvent).content }));
      this.memories = mems;
      this.updateDisplayedEntries();
    });

    // Listen for memory query responses from the backend
    this.outputSub = this.tauri.output$.subscribe((message) => {
      if (message.type === 'memory_results') {
        this.handleMemoryResults(message['results']);
      }
      if (message.type === 'memories_by_date') {
        this.handleMemoriesByDate(message['data']);
      }
      if (message.type === 'available_dates') {
        this.handleAvailableDates(message['data']);
      }
    });
    
    // Fetch available dates for calendar highlighting
    this.fetchAvailableDates();
    
    // Load entries for current date on init
    this.loadEntriesForDate(this.selectedDate);
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.outputSub?.unsubscribe();
  }

  onDateSelected(date: Date | null): void {
    if (date) {
      this.selectedDate = date;
      console.log('Date selected:', this.selectedDate);
      
      // Load entries for the new date
      this.loadEntriesForDate(this.selectedDate);
    }
  }
  
  private loadEntriesForDate(date: Date): void {
    this.isLoadingEntries = true;
    
    // Format date as YYYY-MM-DD
    const dateStr = this.formatDateForBackend(date);
    
    const message: GetMemoriesByDateMessage = {
      type: 'get_memories_by_date',
      date: dateStr,
      timestamp: new Date().toISOString()
    };
    
    this.tauri.send_command(message);
  }
  
  private formatDateForBackend(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  
  private isCurrentDate(): boolean {
    const today = new Date();
    return this.formatDateForBackend(this.selectedDate) === this.formatDateForBackend(today);
  }
  
  private updateDisplayedEntries(): void {
    if (this.isCurrentDate()) {
      // Current date: merge loaded entries + live memories
      // Convert loaded entries to display format
      const loadedAsDisplay = this.loadedEntries.map(entry => ({
        timestamp: entry.inserted_at,
        content: entry.content
      }));
      
      // Merge and sort by timestamp
      const combined = [...loadedAsDisplay, ...this.memories];
      this.displayedEntries = combined.sort((a, b) => 
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );
    } else {
      // Past date: only show loaded entries
      this.displayedEntries = this.loadedEntries.map(entry => ({
        timestamp: entry.inserted_at,
        content: entry.content
      }));
    }
  }

  askLogbookQuestion(): void {
    if (this.logbookQuestion.trim()) {
      console.log('Asking logbook question:', this.logbookQuestion);
      this.isSearching = true;
      this.searchResults = [];
      this.showSearchResults = true; // Auto-show results when searching
      this.hasPerformedSearch = true; // Mark that a search has been performed
      
      // Send command to query memories directly (no LLM interaction)
      const message: QueryMemoriesMessage = {
        type: 'query_memories',
        query: this.logbookQuestion,
        top_k: 5,
        timestamp: new Date().toISOString()
      };
      
      this.tauri.send_command(message);
    }
  }

  toggleSearchResults(): void {
    this.showSearchResults = !this.showSearchResults;
  }

  private handleMemoryResults(response: any): void {
    this.isSearching = false;
    
    try {
      if (response.error) {
        console.error('Error fetching memories:', response.error);
        this.searchResults = [];
        this.showSearchResults = true; // Still show to display error/no results
        return;
      }
      
      if (response.results && Array.isArray(response.results)) {
        this.searchResults = response.results.map((result: any) => ({
          score: result.score,
          summary: result.summary,
          inserted_at: result.inserted_at
        }));
        this.showSearchResults = true; // Ensure results are visible
        console.log('Received memory search results:', this.searchResults);
      } else {
        this.searchResults = [];
        this.showSearchResults = true; // Show to display no results message
      }
    } catch (error) {
      console.error('Error handling memory results:', error);
      this.searchResults = [];
      this.showSearchResults = true;
    }
  }
  
  private handleMemoriesByDate(response: any): void {
    this.isLoadingEntries = false;
    
    try {
      if (response.error) {
        console.error('Error fetching memories by date:', response.error);
        this.loadedEntries = [];
        this.updateDisplayedEntries();
        return;
      }
      
      if (response.entries && Array.isArray(response.entries)) {
        this.loadedEntries = response.entries;
        console.log(`Loaded ${this.loadedEntries.length} entries for date ${response.date}`);
        this.updateDisplayedEntries();
      } else {
        this.loadedEntries = [];
        this.updateDisplayedEntries();
      }
    } catch (error) {
      console.error('Error handling memories by date:', error);
      this.loadedEntries = [];
      this.updateDisplayedEntries();
    }
  }
  
  private fetchAvailableDates(): void {
    const message: GetAvailableDatesMessage = {
      type: 'get_available_dates',
      timestamp: new Date().toISOString()
    };
    
    this.tauri.send_command(message);
  }
  
  private handleAvailableDates(response: any): void {
    try {
      if (response.error) {
        console.error('Error fetching available dates:', response.error);
        this.availableDates = [];
        this.availableDatesSet.clear();
        return;
      }
      
      if (response.dates && Array.isArray(response.dates)) {
        this.availableDates = response.dates;
        // Create a Set for O(1) lookup
        this.availableDatesSet = new Set(response.dates.map((d: DateInfo) => d.date));
        console.log(`Found ${this.availableDates.length} dates with entries`);
      } else {
        this.availableDates = [];
        this.availableDatesSet.clear();
      }
    } catch (error) {
      console.error('Error handling available dates:', error);
      this.availableDates = [];
      this.availableDatesSet.clear();
    }
  }
  
  // Custom date class function for the datepicker
  dateClass = (date: Date | null): string => {
    if (!date) return '';
    const dateStr = this.formatDateForBackend(date);
    return this.availableDatesSet.has(dateStr) ? 'has-entries' : '';
  }
}


