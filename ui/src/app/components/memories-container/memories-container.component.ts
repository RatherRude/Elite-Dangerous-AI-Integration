import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatCardModule } from "@angular/material/card";
import { EventService, MemoryEvent } from "../../services/event.service";
import { TauriService, QueryMemoriesMessage } from "../../services/tauri.service";
import { Subscription } from "rxjs";

interface MemorySearchResult {
  score: number;
  summary: string;
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
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.outputSub?.unsubscribe();
  }

  loadOldEntries(): void {
    console.log('Load old entries clicked', this.selectedDate);
    // TODO: Implement loading old entries from backend
  }

  onDateChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedDate = new Date(input.value);
    console.log('Date changed to:', this.selectedDate);
    // TODO: Load entries for the selected date
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
}


