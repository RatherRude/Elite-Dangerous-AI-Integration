import { Injectable } from '@angular/core';

/** One-time IndexedDB → disk avatar migration result. */
export type LegacyAvatarMigrationOutcome =
  | { status: 'skipped' }
  | { status: 'migrated'; updatedCharacters: unknown[] | null };

interface LegacyIndexedDbAvatarRow {
  id: string;
  imageBlob: Blob;
  uploadTime: Date | string;
  fileName: string;
}

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
  static isIndexedDbAvatarMigrationDone(): boolean {
    return localStorage.getItem('cn_avatar_idb_to_disk_done') === '1';
  }

  static markIndexedDbAvatarMigrationDone(): void {
    localStorage.setItem('cn_avatar_idb_to_disk_done', '1');
  }

  private readonly electronAPI = window.electronAPI;
  private readonly fallbackMimeType = 'application/octet-stream';

  /** Export avatarDB to disk; remap character.avatar from IndexedDB id to filename where needed. */
  async migrateFromLegacyIndexedDb(characters: unknown[]): Promise<LegacyAvatarMigrationOutcome> {
    if (AvatarService.isIndexedDbAvatarMigrationDone()) {
      return { status: 'skipped' };
    }
    if (!this.electronAPI?.invoke) {
      return { status: 'skipped' };
    }

    const dbPresent = await this.legacyAvatarIndexedDbExists();
    if (!dbPresent) {
      AvatarService.markIndexedDbAvatarMigrationDone();
      return { status: 'skipped' };
    }

    const rows = await this.readLegacyIndexedDbAvatarRows();
    if (rows.length === 0) {
      await this.deleteLegacyAvatarIndexedDb();
      AvatarService.markIndexedDbAvatarMigrationDone();
      return { status: 'skipped' };
    }

    const idToFileName = new Map<string, string>();
    for (const row of rows) {
      const blob =
        row.imageBlob instanceof Blob
          ? row.imageBlob
          : new Blob([], { type: this.fallbackMimeType });
      const requestedName = row.fileName?.trim() || `avatar_${row.id}.png`;
      const diskName = await this.persistLegacyAvatarBlob(requestedName, blob);
      idToFileName.set(row.id, diskName);
    }

    let anyCharacterUpdate = false;
    const updatedCharacters = characters.map((raw) => {
      const ch = { ...(raw as Record<string, unknown>) };
      const ref = ch['avatar'];
      if (typeof ref === 'string' && ref && idToFileName.has(ref)) {
        ch['avatar'] = idToFileName.get(ref)!;
        anyCharacterUpdate = true;
      }
      return ch;
    });

    return {
      status: 'migrated',
      updatedCharacters: anyCharacterUpdate ? updatedCharacters : null,
    };
  }

  /** Remove legacy DB after blobs are on disk and config has been saved (if needed). */
  async deleteLegacyAvatarIndexedDb(): Promise<void> {
    await new Promise<void>((resolve, reject) => {
      const req = indexedDB.deleteDatabase('avatarDB');
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error ?? new Error('deleteDatabase failed'));
      req.onblocked = () => resolve();
    });
  }

  private async legacyAvatarIndexedDbExists(): Promise<boolean> {
    try {
      if (indexedDB.databases) {
        const dbs = await indexedDB.databases();
        return dbs.some((d) => d.name === 'avatarDB');
      }
    } catch {
      /* fall through */
    }
    return true;
  }

  private readLegacyIndexedDbAvatarRows(): Promise<LegacyIndexedDbAvatarRow[]> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('avatarDB', 1);
      request.onerror = () => resolve([]);
      request.onsuccess = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains('avatars')) {
          db.close();
          resolve([]);
          return;
        }
        const tx = db.transaction('avatars', 'readonly');
        const store = tx.objectStore('avatars');
        const allReq = store.getAll();
        allReq.onsuccess = () => {
          db.close();
          resolve((allReq.result as LegacyIndexedDbAvatarRow[]) ?? []);
        };
        allReq.onerror = () => {
          db.close();
          reject(allReq.error ?? new Error('getAll failed'));
        };
      };
    });
  }

  /** Prefer original fileName; if that file already exists on disk, use avatar_upload for a unique name. */
  private async persistLegacyAvatarBlob(fileName: string, blob: Blob): Promise<string> {
    this.ensureElectronApi();
    const dataBase64 = await this.blobToBase64(blob);
    const mimeType = blob.type || this.fallbackMimeType;
    const writeResult = (await this.electronAPI.invoke('avatar_write_file', {
      fileName,
      mimeType,
      dataBase64,
      overwrite: false,
    })) as { written: boolean; fileName: string };

    if (writeResult.written) {
      return writeResult.fileName;
    }

    const uploadResult = (await this.electronAPI.invoke('avatar_upload', {
      fileName,
      mimeType,
      dataBase64,
    })) as { fileName: string };
    return uploadResult.fileName;
  }

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