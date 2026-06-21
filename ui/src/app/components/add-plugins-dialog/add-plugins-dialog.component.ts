import { Component, Inject, OnInit } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';

export interface PluginInfo {
  id: string;
  name: string;
  description: string;
  author: string;
  version: string;
  repo: string;
  downloadUrl: string;
}

export interface PluginsCatalog {
  plugins: PluginInfo[];
}

@Component({
  selector: 'app-add-plugins-dialog',
  templateUrl: './add-plugins-dialog.component.html',
  styleUrls: ['./add-plugins-dialog.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatCardModule,
    MatIconModule,
    MatChipsModule
  ]
})
export class AddPluginsDialogComponent implements OnInit {
  plugins: PluginInfo[] = [];
  loading = true;
  error: string | null = null;
  installingPlugins: Set<string> = new Set();

  constructor(
    public dialogRef: MatDialogRef<AddPluginsDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: any,
    private http: HttpClient
  ) {}

  ngOnInit() {
    this.loadPlugins();
  }

  loadPlugins() {
    this.loading = true;
    this.error = null;
    
    this.http.get<PluginsCatalog>('assets/plugins-catalog.json').subscribe({
      next: (data) => {
        this.plugins = data.plugins || [];
        this.loading = false;
      },
      error: (err) => {
        console.error('Error loading plugins catalog:', err);
        this.error = 'Failed to load plugins catalog';
        this.loading = false;
      }
    });
  }

  onClose(): void {
    this.dialogRef.close();
  }

  async openRepo(repo: string): Promise<void> {
    try {
      if (typeof window !== 'undefined' && (window as any).electronAPI?.invoke) {
        await (window as any).electronAPI.invoke('open-external', repo);
      } else {
        window.open(repo, '_blank');
      }
    } catch (error) {
      console.error('Error opening repository:', error);
      window.open(repo, '_blank');
    }
  }

  isInstalling(pluginId: string): boolean {
    return this.installingPlugins.has(pluginId);
  }

  async installPlugin(plugin: PluginInfo): Promise<void> {
    if (this.installingPlugins.has(plugin.id)) {
      return; // Already installing
    }

    this.installingPlugins.add(plugin.id);
    
    try {
      if (typeof window !== 'undefined' && (window as any).electronAPI?.invoke) {
        await (window as any).electronAPI.invoke('install-plugin', {
          repo: plugin.repo,
          pluginId: plugin.id
        });
        // Window will reload after installation, so we don't need to remove from set
      } else {
        this.error = 'Electron API not available. Cannot install plugins.';
        this.installingPlugins.delete(plugin.id);
      }
    } catch (error) {
      console.error('Error installing plugin:', error);
      this.error = `Failed to install ${plugin.name}: ${error}`;
      this.installingPlugins.delete(plugin.id);
    }
  }
}
