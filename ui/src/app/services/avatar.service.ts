import { Injectable } from '@angular/core';

export interface AvatarData {
  path: string;
  fileName: string;
  uploadTime: Date;
  mimeType?: string;
  size?: number;
}

interface StoredAvatarFile {
  path: string;
  fileName: string;
  mimeType?: string;
  createdAt?: string;
  modifiedAt?: string;
  size?: number;
}

@Injectable({
  providedIn: 'root'
})
export class AvatarService {
  public isAbsoluteFilePath(reference: string | null | undefined): boolean {
    if (!reference) {
      return false;
    }
    return reference.startsWith('/') || /^[A-Za-z]:[\\/]/.test(reference) || reference.startsWith('\\\\');
  }

  public isDirectUrl(reference: string | null | undefined): boolean {
    if (!reference) {
      return false;
    }
    return /^(https?:|data:|blob:|file:)/i.test(reference);
  }

  public isObjectUrl(url: string | null | undefined): boolean {
    return typeof url === 'string' && url.startsWith('blob:');
  }

  async uploadAvatar(file: File): Promise<string> {
    return this.writeAvatarBlob(file, file.name, file.type || undefined);
  }

  async writeAvatarBlob(blob: Blob, fileName: string, mimeType?: string): Promise<string> {
    const electronAPI = this.getElectronAPI();
    const dataBase64 = await this.blobToBase64(blob);
    const response = await (electronAPI.userAssets?.writeFile
      ? electronAPI.userAssets.writeFile({ fileName, mimeType, dataBase64 })
      : electronAPI.invoke('write_user_asset_file', { fileName, mimeType, dataBase64 }));
    if (!response?.path || typeof response.path !== 'string') {
      throw new Error('Avatar write failed: invalid response');
    }
    return response.path;
  }

  async getAvatar(reference: string): Promise<string | null> {
    const meta = await this.getAvatarWithMime(reference);
    return meta?.url ?? null;
  }

  /** Same as getAvatar but includes stored MIME (for overlay sprite vs single-image layout). */
  async getAvatarWithMime(reference: string): Promise<{ url: string; mimeType: string } | null> {
    if (!reference) {
      return null;
    }
    if (this.isDirectUrl(reference)) {
      return {
        url: reference,
        mimeType: this.inferMimeType(reference),
      };
    }
    if (!this.isAbsoluteFilePath(reference)) {
      return null;
    }
    const file = await this.readAvatarFile(reference);
    if (!file) {
      return null;
    }
    const mimeType = (file.mimeType || 'application/octet-stream').trim();
    const blob = await this.base64ToBlob(file.dataBase64, mimeType);
    return {
      url: URL.createObjectURL(blob),
      mimeType: blob.type || mimeType,
    };
  }

  async getAllAvatars(): Promise<AvatarData[]> {
    const electronAPI = this.getElectronAPI();
    const response = await (electronAPI.userAssets?.listFiles
      ? electronAPI.userAssets.listFiles()
      : electronAPI.invoke('list_user_asset_files'));
    if (!Array.isArray(response)) {
      throw new Error('Avatar list failed: invalid response');
    }
    return response.map((entry: StoredAvatarFile) => ({
      path: entry.path,
      fileName: entry.fileName,
      uploadTime: new Date(entry.createdAt || entry.modifiedAt || Date.now()),
      mimeType: entry.mimeType,
      size: entry.size,
    }));
  }

  async deleteAvatar(reference: string): Promise<void> {
    if (!reference || !this.isAbsoluteFilePath(reference)) {
      return;
    }
    const electronAPI = this.getElectronAPI();
    await (electronAPI.userAssets?.deleteFile
      ? electronAPI.userAssets.deleteFile({ path: reference })
      : electronAPI.invoke('delete_user_asset_file', { path: reference }));
  }

  async getAvatarBlob(reference: string): Promise<Blob | null> {
    if (!reference) {
      return null;
    }
    if (this.isDirectUrl(reference)) {
      const response = await fetch(reference);
      return response.blob();
    }
    if (!this.isAbsoluteFilePath(reference)) {
      return null;
    }
    const file = await this.readAvatarFile(reference);
    if (!file) {
      return null;
    }
    return this.base64ToBlob(file.dataBase64, file.mimeType || 'application/octet-stream');
  }

  private getElectronAPI() {
    const electronAPI = window.electronAPI;
    if (!electronAPI) {
      throw new Error('Electron API not available');
    }
    return electronAPI;
  }

  private async readAvatarFile(filePath: string): Promise<{ dataBase64: string; mimeType: string } | null> {
    const electronAPI = this.getElectronAPI();
    const response = await (electronAPI.userAssets?.readFile
      ? electronAPI.userAssets.readFile({ path: filePath })
      : electronAPI.invoke('read_user_asset_file', { path: filePath }));
    if (!response?.dataBase64 || typeof response.dataBase64 !== 'string') {
      return null;
    }
    return {
      dataBase64: response.dataBase64,
      mimeType: typeof response.mimeType === 'string' ? response.mimeType : 'application/octet-stream',
    };
  }

  private inferMimeType(reference: string): string {
    if (reference.startsWith('data:')) {
      const match = /^data:([^;,]+)/i.exec(reference);
      if (match?.[1]) {
        return match[1];
      }
    }
    const normalized = reference.split('?')[0].split('#')[0].toLowerCase();
    if (normalized.endsWith('.svg')) {
      return 'image/svg+xml';
    }
    if (normalized.endsWith('.png')) {
      return 'image/png';
    }
    if (normalized.endsWith('.jpg') || normalized.endsWith('.jpeg')) {
      return 'image/jpeg';
    }
    if (normalized.endsWith('.webp')) {
      return 'image/webp';
    }
    if (normalized.endsWith('.gif')) {
      return 'image/gif';
    }
    return 'application/octet-stream';
  }

  private async blobToBase64(blob: Blob): Promise<string> {
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

  private async base64ToBlob(base64: string, mimeType: string): Promise<Blob> {
    const response = await fetch(`data:${mimeType};base64,${base64}`);
    return response.blob();
  }
}
