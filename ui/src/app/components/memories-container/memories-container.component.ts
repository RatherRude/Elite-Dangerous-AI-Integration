import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatCardModule } from "@angular/material/card";
import { EventService, MemoryEvent } from "../../services/event.service";
import { TauriService, QueryMemoriesMessage, GetMemoriesByDateMessage } from "../../services/tauri.service";
import { Subscription } from "rxjs";

interface MemorySearchResult {
  score: number;
  summary: string;
}

interface MemoryEntry {
  id: number;
  content: string;
  inserted_at: string;
  metadata: Record<string, any>;
}

@Component({
  selector: "app-memories-container",
  standalone: true,
  imports: [CommonModule, MatCardModule, FormsModule],
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
  public loadedEntries: MemoryEntry[] = [];
  public filteredEntries: MemoryEntry[] = [];
  public isLoadingEntries: boolean = false;

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
    });

    // Listen for memory query responses from the backend
    this.outputSub = this.tauri.output$.subscribe((message) => {
      if (message.type === 'memory_results') {
        this.handleMemoryResults(message['results']);
      }
      if (message.type === 'memories_by_date') {
        this.handleMemoriesByDate(message['data']);
      }
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.outputSub?.unsubscribe();
  }

  loadOldEntries(): void {
    console.log('Load old entries clicked', this.selectedDate);
    this.isLoadingEntries = true;
    
    // Format date as YYYY-MM-DD
    const dateStr = this.formatDateForBackend(this.selectedDate);
    
    const message: GetMemoriesByDateMessage = {
      type: 'get_memories_by_date',
      date: dateStr,
      timestamp: new Date().toISOString()
    };
    
    this.tauri.send_command(message);
  }

  onDateChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedDate = new Date(input.value);
    console.log('Date changed to:', this.selectedDate);
    
    // If entries are already loaded, filter them by the new date
    if (this.loadedEntries.length > 0) {
      this.filterEntriesByDate();
    }
  }
  
  private formatDateForBackend(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  
  private filterEntriesByDate(): void {
    const targetDateStr = this.formatDateForBackend(this.selectedDate);
    
    this.filteredEntries = this.loadedEntries.filter(entry => {
      if (!entry.inserted_at) return false;
      const entryDate = entry.inserted_at.split('T')[0]; // Extract YYYY-MM-DD
      return entryDate === targetDateStr;
    });
    
    console.log(`Filtered to ${this.filteredEntries.length} entries for ${targetDateStr}`);
  }

  openCalendar(): void {
    console.log('Open calendar clicked');
    // The native date input will handle the calendar display
    const dateInput = document.querySelector('.date-input') as HTMLInputElement;
    if (dateInput) {
      dateInput.showPicker();
    }
  }

  askLogbookQuestion(): void {
    if (this.logbookQuestion.trim()) {
      console.log('Asking logbook question:', this.logbookQuestion);
      this.isSearching = true;
      this.searchResults = [];
      
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
        return;
      }
      
      if (response.results && Array.isArray(response.results)) {
        this.searchResults = response.results.map((result: any) => ({
          score: result.score,
          summary: result.summary
        }));
        this.showSearchResults = true;
        console.log('Received memory search results:', this.searchResults);
      } else {
        this.searchResults = [];
      }
    } catch (error) {
      console.error('Error handling memory results:', error);
      this.searchResults = [];
    }
  }
  
  private handleMemoriesByDate(response: any): void {
    this.isLoadingEntries = false;
    
    try {
      if (response.error) {
        console.error('Error fetching memories by date:', response.error);
        this.loadedEntries = [];
        this.filteredEntries = [];
        return;
      }
      
      if (response.entries && Array.isArray(response.entries)) {
        this.loadedEntries = response.entries;
        this.filteredEntries = response.entries; // Initially show all loaded entries
        console.log(`Loaded ${this.loadedEntries.length} entries for date ${response.date}`);
      } else {
        this.loadedEntries = [];
        this.filteredEntries = [];
      }
    } catch (error) {
      console.error('Error handling memories by date:', error);
      this.loadedEntries = [];
      this.filteredEntries = [];
    }
  }
}


