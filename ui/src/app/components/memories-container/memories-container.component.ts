import { Component, OnDestroy, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import { EventService, MemoryEvent } from "../../services/event.service";
import { Subscription } from "rxjs";

@Component({
  selector: "app-memories-container",
  standalone: true,
  imports: [CommonModule, MatCardModule],
  templateUrl: "./memories-container.component.html",
  styleUrls: ["./memories-container.component.css"],
})
export class MemoriesContainerComponent implements OnInit, OnDestroy {
  private sub?: Subscription;
  public memories: { timestamp: string; content: string }[] = [];

  constructor(private events: EventService) {}

  ngOnInit(): void {
    this.sub = this.events.events$.subscribe((all) => {
      const mems = all
        .map((m) => m.event)
        .filter((e): e is MemoryEvent => (e as any)?.kind === "memory")
        .map((e) => ({ timestamp: (e as MemoryEvent).timestamp, content: (e as MemoryEvent).content }));
      this.memories = mems;
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}


