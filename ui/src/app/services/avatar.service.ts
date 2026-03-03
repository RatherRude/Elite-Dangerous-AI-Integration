import { Injectable } from '@angular/core';

export interface AvatarData {
  id: string;
  imageBlob: Blob;
  uploadTime: Date;
  fileName: string;
}

interface AvatarPayload {
  fileName: string;
  dataBase64: string;
  uploadTime: string;
  mimeType: string;
}

interface AvatarListItem {
  fileName: string;
  uploadTime: string;
  mimeType: string;
}

@Injectable({
  providedIn: 'root'
})
export class AvatarService {
  private readonly electronAPI = window.electronAPI;
  private readonly fallbackMimeType = 'application/octet-stream';

  async uploadAvatar(file: File): Promise<string> {
    this.ensureElectronApi();
    const dataBase64 = await this.blobToBase64(file);
    const result = await this.electronAPI.invoke('avatar_upload', {
      fileName: file.name,
      mimeType: file.type || this.fallbackMimeType,
      dataBase64,
    });
    return result.fileName as string;
  }

  async getAvatar(id: string): Promise<string | null> {
    const payload = await this.readAvatarPayload(id);
    if (!payload) {
      return null;
    }
    const blob = this.base64ToBlob(payload.dataBase64, payload.mimeType);
    return URL.createObjectURL(blob);
  }

  async getAllAvatars(): Promise<AvatarData[]> {
    this.ensureElectronApi();
    const list = await this.electronAPI.invoke('avatar_get_all') as AvatarListItem[];
    const avatars = await Promise.all(
      list.map(async (item) => {
        const payload = await this.readAvatarPayload(item.fileName);
        if (!payload) {
          return null;
        }
        return {
          id: item.fileName,
          imageBlob: this.base64ToBlob(payload.dataBase64, payload.mimeType),
          uploadTime: new Date(payload.uploadTime || item.uploadTime),
          fileName: item.fileName,
        } as AvatarData;
      }),
    );
    return avatars
      .filter((avatar): avatar is AvatarData => avatar !== null)
      .sort((a, b) => b.uploadTime.getTime() - a.uploadTime.getTime());
  }

  async deleteAvatar(id: string): Promise<void> {
    this.ensureElectronApi();
    await this.electronAPI.invoke('avatar_delete', { fileName: id });
  }

  async getAvatarBlob(id: string): Promise<Blob | null> {
    const payload = await this.readAvatarPayload(id);
    if (!payload) {
      return null;
    }
    return this.base64ToBlob(payload.dataBase64, payload.mimeType);
  }

  async avatarExists(fileName: string): Promise<boolean> {
    this.ensureElectronApi();
    return await this.electronAPI.invoke('avatar_exists', { fileName }) as boolean;
  }

  async writeAvatarWithFileName(fileName: string, imageBlob: Blob, overwrite = false): Promise<boolean> {
    this.ensureElectronApi();
    const dataBase64 = await this.blobToBase64(imageBlob);
    const result = await this.electronAPI.invoke('avatar_write_file', {
      fileName,
      mimeType: imageBlob.type || this.fallbackMimeType,
      dataBase64,
      overwrite,
    });
    return result.written === true;
  }

  private async readAvatarPayload(fileName: string): Promise<AvatarPayload | null> {
    this.ensureElectronApi();
    if (!fileName) {
      return null;
    }
    return await this.electronAPI.invoke('avatar_get', { fileName }) as AvatarPayload | null;
  }

  private ensureElectronApi(): void {
    if (!this.electronAPI?.invoke) {
      throw new Error('electronAPI not available');
    }
  }

  private blobToBase64(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1] || '');
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  private base64ToBlob(dataBase64: string, mimeType: string): Blob {
    const binary = atob(dataBase64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }
    return new Blob([bytes], { type: mimeType || this.fallbackMimeType });
  }
} 