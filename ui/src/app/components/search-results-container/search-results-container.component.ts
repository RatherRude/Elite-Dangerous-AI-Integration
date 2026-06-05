import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatCardModule } from "@angular/material/card";
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { ChatMessage, ChatService } from "../../services/chat.service";
import { TauriService } from "../../services/tauri.service";
import { Subscription } from "rxjs";
import { MarkdownModule } from 'ngx-markdown';

@Component({
  selector: "app-search-results-container",
  standalone: true,
  imports: [
    CommonModule, 
    MatCardModule, 
    FormsModule,
    MatInputModule,
    MatFormFieldModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MarkdownModule
  ],
  templateUrl: "./search-results-container.component.html",
  styleUrls: ["./search-results-container.component.scss"]
})
export class SearchResultsComponent implements OnInit, OnDestroy {
  searchQuery: string = "";
  searchResult: string | null = null;
  searchError: string | null = null;
  isLoading: boolean = false;
  private searchResultSubscription: Subscription | null = null;
  private errorMessageSubscription: Subscription | null = null;

  constructor(private chatService: ChatService, private tauriService: TauriService) {}

  ngOnInit(): void {
    this.searchResultSubscription = this.chatService.searchResult$.subscribe(result => {
      if (!result) {
        return;
      }

      this.isLoading = false;
      this.searchError = null;

      if (result.content && typeof result.content === 'string') {
        const content = result.content.trim();
        if (this.isSearchError(content)) {
          this.searchResult = null;
          this.searchError = content;
          return;
        }

        this.searchResult = content;
        return;
      }

      this.searchResult = JSON.stringify(result, null, 2);
    });

    this.errorMessageSubscription = this.chatService.chatMessage$.subscribe((message: ChatMessage | null) => {
      if (!this.isLoading || !message || message.role?.toLowerCase() !== 'error') {
        return;
      }

      this.isLoading = false;
      this.searchResult = null;
      this.searchError = message.message || 'An unknown search error occurred.';
    });
  }

  ngOnDestroy(): void {
    if (this.searchResultSubscription) {
      this.searchResultSubscription.unsubscribe();
    }
    if (this.errorMessageSubscription) {
      this.errorMessageSubscription.unsubscribe();
    }
  }

  search(): void {
    if (!this.searchQuery.trim()) return;
    
    this.isLoading = true;
    this.searchResult = null;
    this.searchError = null;
    this.tauriService.send_command({
      type: "web_search",
      query: this.searchQuery,
      timestamp: new Date().toISOString()
    });
  }

  private isSearchError(content: string): boolean {
    return /^(error|llm error)\s*:/i.test(content);
  }
}
