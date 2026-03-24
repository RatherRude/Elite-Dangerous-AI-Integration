import { Injectable } from '@angular/core';
import { ConfigService, Config } from './config.service';
import { AvatarService } from './avatar.service';

export interface BackupData {
  version: number;
  timestamp: string;
  config: Config;
  avatars: Array<{
    path?: string;
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

      // Get all avatars from filesystem-backed avatar storage
      const avatars = await this.avatarService.getAllAvatars();

      // Convert avatar blobs to base64
      const avatarsData = await Promise.all(
        avatars.map(async (avatar) => {
          const blob = await this.avatarService.getAvatarBlob(avatar.path);
          if (!blob) {
            throw new Error(`Unable to read avatar file for backup: ${avatar.path}`);
          }
          const base64 = await this.blobToBase64(blob);
          return {
            path: avatar.path,
            imageData: base64,
            uploadTime: avatar.uploadTime.toISOString(),
            fileName: avatar.fileName,
            mimeType: blob.type || avatar.mimeType || 'application/octet-stream'
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

      // Import avatars first and remap stored references to new local file paths.
      let importedAvatars = 0;
      const avatarPathMap = new Map<string, string>();
      
      for (const avatarData of backupData.avatars) {
        try {
          // Convert base64 back to Blob
          const blob = await this.base64ToBlob(avatarData.imageData, avatarData.mimeType);
          const newPath = await this.avatarService.writeAvatarBlob(
            blob,
            avatarData.fileName,
            avatarData.mimeType,
          );
          if (avatarData.path) {
            avatarPathMap.set(avatarData.path, newPath);
          }
          importedAvatars++;
        } catch (error) {
          console.error(`Error importing avatar ${avatarData.path || avatarData.fileName}:`, error);
          // Continue with other avatars even if one fails
        }
      }

      // Import configuration
      const importedConfig: Config = JSON.parse(JSON.stringify(backupData.config));
      if (Array.isArray(importedConfig.characters)) {
        importedConfig.characters = importedConfig.characters.map((character: any) => {
          if (!character || typeof character !== 'object' || typeof character.avatar !== 'string') {
            return character;
          }
          const mappedPath = avatarPathMap.get(character.avatar);
          return mappedPath ? { ...character, avatar: mappedPath } : character;
        });
      }
      await this.configService.changeConfig(importedConfig);

      const message = `Successfully imported configuration with ${importedAvatars} avatar(s)`;
      
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
