import { Injectable } from '@angular/core';
import { ConfigService, Config } from './config.service';
import { AvatarService } from './avatar.service';

export interface BackupData {
  version: number;
  timestamp: string;
  config: Config;
  avatars: Array<{
    id: string;
    imageData: string; // base64 encoded
    uploadTime: string;
    fileName: string;
    mimeType: string;
  }>;
}

@Injectable({
  providedIn: 'root'
})
export class ConfigBackupService {

  constructor(
    private configService: ConfigService,
    private avatarService: AvatarService
  ) {}

  /**
   * Export configuration and avatars to a JSON file
   */
  async exportConfig(): Promise<void> {
    try {
      // Get current config
      const config = this.configService.getCurrentConfig();
      if (!config) {
        throw new Error('No configuration available to export');
      }

      // Get all avatars from disk-based avatar storage
      const avatars = await this.avatarService.getAllAvatars();

      // Convert avatar blobs to base64
      const avatarsData = await Promise.all(
        avatars.map(async (avatar) => {
          const base64 = await this.blobToBase64(avatar.imageBlob);
          return {
            id: avatar.id,
            imageData: base64,
            uploadTime: avatar.uploadTime.toISOString(),
            fileName: avatar.fileName,
            mimeType: avatar.imageBlob.type
          };
        })
      );

      // Create backup data
      const backupData: BackupData = {
        version: config['config_version'],
        timestamp: new Date().toISOString(),
        config: config,
        avatars: avatarsData
      };

      // Convert to JSON
      const jsonString = JSON.stringify(backupData, null, 2);
      const blob = new Blob([jsonString], { type: 'application/json' });

      // Generate filename with date
      const now = new Date();
      const day = String(now.getDate()).padStart(2, '0');
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const year = now.getFullYear();
      const filename = `COVAS_NEXT ${day} ${month} ${year}.json`;

      // Trigger download
      this.downloadBlob(blob, filename);
    } catch (error) {
      console.error('Error exporting configuration:', error);
      throw error;
    }
  }

  /**
   * Import configuration and avatars from a JSON file
   */
  async importConfig(file: File): Promise<{ success: boolean; message: string }> {
    try {
      // Read file content
      const fileContent = await this.readFileAsText(file);
      const backupData: BackupData = JSON.parse(fileContent);

      // Validate backup data
      if (!backupData.config || !backupData.avatars) {
        throw new Error('Invalid backup file format');
      }

      // Import avatars first
      let importedAvatars = 0;
      let skippedAvatars = 0;
      
      for (const avatarData of backupData.avatars) {
        try {
          // Convert base64 back to Blob
          const blob = await this.base64ToBlob(avatarData.imageData, avatarData.mimeType);

          // Check if avatar already exists by filename
          const existingAvatar = await this.avatarService.avatarExists(avatarData.id);

          if (existingAvatar) {
            // Avatar already exists, skip it
            skippedAvatars++;
            console.log(`Avatar ${avatarData.id} already exists, skipping...`);
          } else {
            // Import avatar with the original filename so config references remain valid
            const written = await this.avatarService.writeAvatarWithFileName(
              avatarData.id,
              blob,
              false,
            );
            if (written) {
              importedAvatars++;
            } else {
              skippedAvatars++;
            }
          }
        } catch (error) {
          console.error(`Error importing avatar ${avatarData.id}:`, error);
          // Continue with other avatars even if one fails
        }
      }

      // Import configuration
      await this.configService.changeConfig(backupData.config);

      const message = `Successfully imported configuration with ${importedAvatars} avatar(s)` + 
                     (skippedAvatars > 0 ? ` (${skippedAvatars} avatar(s) skipped - already exist)` : '');
      
      return {
        success: true,
        message: message
      };
    } catch (error) {
      console.error('Error importing configuration:', error);
      return {
        success: false,
        message: error instanceof Error ? error.message : 'Unknown error occurred'
      };
    }
  }

  /**
   * Convert Blob to base64 string
   */
  private blobToBase64(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const result = reader.result as string;
        // Remove data URL prefix (e.g., "data:image/png;base64,")
        const base64 = result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  /**
   * Convert base64 string to Blob
   */
  private async base64ToBlob(base64: string, mimeType: string): Promise<Blob> {
    const response = await fetch(`data:${mimeType};base64,${base64}`);
    return response.blob();
  }

  /**
   * Read file content as text
   */
  private readFileAsText(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsText(file);
    });
  }

  /**
   * Download blob as file
   */
  private downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
}


