import { Injectable } from '@angular/core';

export interface AvatarData {
  id: string;
  imageBlob: Blob;
  uploadTime: Date;
  fileName: string;
}

@Injectable({
  providedIn: 'root'
})
export class AvatarService {
  private dbName = 'avatarDB';
  private dbVersion = 1;
  private storeName = 'avatars';
  private db: IDBDatabase | null = null;

  constructor() {
    this.initDB();
  }

  private async initDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.dbVersion);

      request.onerror = () => {
        reject(request.error);
      };

      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          const store = db.createObjectStore(this.storeName, { keyPath: 'id' });
          store.createIndex('uploadTime', 'uploadTime', { unique: false });
        }
      };
    });
  }

  async uploadAvatar(file: File): Promise<string> {
    await this.ensureDBReady();
    
    const id = this.generateAvatarId();
    const avatarData: AvatarData = {
      id,
      imageBlob: file,
      uploadTime: new Date(),
      fileName: file.name
    };

    return new Promise((resolve, reject) => {
      if (!this.db) {
        reject(new Error('Database not initialized'));
        return;
      }

      const transaction = this.db.transaction([this.storeName], 'readwrite');
      const store = transaction.objectStore(this.storeName);
      const request = store.add(avatarData);

      request.onsuccess = () => {
        resolve(id);
      };

      request.onerror = () => {
        reject(request.error);
      };
    });
  }

  async getAvatar(id: string): Promise<string | null> {
    await this.ensureDBReady();

    return new Promise((resolve, reject) => {
      if (!this.db) {
        reject(new Error('Database not initialized'));
        return;
      }

      const transaction = this.db.transaction([this.storeName], 'readonly');
      const store = transaction.objectStore(this.storeName);
      const request = store.get(id);

      request.onsuccess = () => {
        const result = request.result as AvatarData;
        if (result) {
          const url = URL.createObjectURL(result.imageBlob);
          resolve(url);
        } else {
          resolve(null);
        }
      };

      request.onerror = () => {
        reject(request.error);
      };
    });
  }

  async getAllAvatars(): Promise<AvatarData[]> {
    await this.ensureDBReady();

    return new Promise((resolve, reject) => {
      if (!this.db) {
        reject(new Error('Database not initialized'));
        return;
      }

      const transaction = this.db.transaction([this.storeName], 'readonly');
      const store = transaction.objectStore(this.storeName);
      const request = store.getAll();

      request.onsuccess = () => {
        const avatars = request.result as AvatarData[];
        // Sort by upload time, newest first
        avatars.sort((a, b) => b.uploadTime.getTime() - a.uploadTime.getTime());
        resolve(avatars);
      };

      request.onerror = () => {
        reject(request.error);
      };
    });
  }

  async deleteAvatar(id: string): Promise<void> {
    await this.ensureDBReady();

    return new Promise((resolve, reject) => {
      if (!this.db) {
        reject(new Error('Database not initialized'));
        return;
      }

      const transaction = this.db.transaction([this.storeName], 'readwrite');
      const store = transaction.objectStore(this.storeName);
      const request = store.delete(id);

      request.onsuccess = () => {
        resolve();
      };

      request.onerror = () => {
        reject(request.error);
      };
    });
  }

  async getAvatarBlob(id: string): Promise<Blob | null> {
    await this.ensureDBReady();

    return new Promise((resolve, reject) => {
      if (!this.db) {
        reject(new Error('Database not initialized'));
        return;
      }

      const transaction = this.db.transaction([this.storeName], 'readonly');
      const store = transaction.objectStore(this.storeName);
      const request = store.get(id);

      request.onsuccess = () => {
        const result = request.result as AvatarData;
        if (result) {
          resolve(result.imageBlob);
        } else {
          resolve(null);
        }
      };

      request.onerror = () => {
        reject(request.error);
      };
    });
  }

  private async ensureDBReady(): Promise<void> {
    if (!this.db) {
      await this.initDB();
    }
  }

  private generateAvatarId(): string {
    return 'avatar_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  }
} 