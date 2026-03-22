import { Injectable } from '@angular/core';
import { combineLatest, filter, take } from 'rxjs';
import { AvatarService } from './avatar.service';
import { Character, ConfigWithCharacters } from './character.service';
import { ConfigService } from './config.service';
import { QuestActor, QuestCatalog, QuestsService } from './quests.service';
import { BaseMessage, TauriService } from './tauri.service';

interface LegacyAvatarData {
  id: string;
  imageBlob: Blob;
  uploadTime: Date;
  fileName: string;
}

@Injectable({
  providedIn: 'root'
})
export class AvatarMigrationService {
  private readonly dbName = 'avatarDB';
  private readonly dbVersion = 1;
  private readonly storeName = 'avatars';
  private readonly legacyReferenceMap = new Map<string, string>();
  private readonly legacyMigrationPromises = new Map<string, Promise<string | null>>();
  private db: IDBDatabase | null = null;
  private characterMigrationPromise: Promise<void> | null = null;
  private questMigrationPromise: Promise<void> | null = null;

  constructor(
    private tauriService: TauriService,
    private configService: ConfigService,
    private questsService: QuestsService,
    private avatarService: AvatarService,
  ) {}

  init(): void {
    const ready$ = this.tauriService.output$.pipe(
      filter((message: BaseMessage) => message.type === 'ready'),
      take(1),
    );

    combineLatest([
      ready$,
      this.configService.config$.pipe(filter((config): config is ConfigWithCharacters => Boolean(config))),
    ]).subscribe(([, config]) => {
      void this.ensureCharacterMigration(config);
    });

    combineLatest([
      ready$,
      this.questsService.catalog$.pipe(filter((catalog): catalog is QuestCatalog => Boolean(catalog))),
      this.questsService.catalogPath$.pipe(filter((catalogPath): catalogPath is string => Boolean(catalogPath))),
    ]).subscribe(([, catalog, catalogPath]) => {
      void this.ensureQuestMigration(catalog, catalogPath);
    });
  }

  private async ensureCharacterMigration(config: ConfigWithCharacters | null): Promise<void> {
    if (!config) {
      return;
    }
    if (this.characterMigrationPromise) {
      await this.characterMigrationPromise;
      return;
    }
    const characters = Array.isArray(config.characters) ? config.characters : [];
    if (!characters.some((character) => this.hasLegacyCharacterAvatar(character))) {
      return;
    }

    this.characterMigrationPromise = this.migrateCharacters(config);
    try {
      await this.characterMigrationPromise;
    } finally {
      this.characterMigrationPromise = null;
      const latestConfig = this.configService.getCurrentConfig() as ConfigWithCharacters | null;
      if (latestConfig && latestConfig !== config) {
        void this.ensureCharacterMigration(latestConfig);
      }
    }
  }

  private async migrateCharacters(config: ConfigWithCharacters): Promise<void> {
    const characters = Array.isArray(config.characters) ? config.characters : [];
    let changed = false;
    const updatedCharacters = await Promise.all(characters.map(async (character) => {
      if (!this.hasLegacyCharacterAvatar(character)) {
        return character;
      }
      const migratedPath = await this.migrateLegacyReference(character.avatar || '');
      if (!migratedPath) {
        console.warn('Unable to migrate legacy character avatar reference:', character.avatar);
        return character;
      }
      changed = true;
      return {
        ...character,
        avatar: migratedPath,
      } as Character;
    }));

    if (!changed) {
      return;
    }
    await this.configService.changeConfig({
      characters: updatedCharacters,
    });
  }

  private async ensureQuestMigration(catalog: QuestCatalog, catalogPath: string): Promise<void> {
    if (this.questMigrationPromise) {
      await this.questMigrationPromise;
      return;
    }
    const actors = Array.isArray(catalog.actors) ? catalog.actors : [];
    if (!actors.some((actor) => this.hasLegacyQuestAvatar(actor))) {
      return;
    }

    this.questMigrationPromise = this.migrateQuestCatalog(catalog, catalogPath);
    try {
      await this.questMigrationPromise;
    } finally {
      this.questMigrationPromise = null;
      const latestCatalog = this.questsService.getCurrentCatalog();
      const latestCatalogPath = this.questsService.getCurrentCatalogPath();
      if (latestCatalog && latestCatalogPath && (latestCatalog !== catalog || latestCatalogPath !== catalogPath)) {
        void this.ensureQuestMigration(latestCatalog, latestCatalogPath);
      }
    }
  }

  private async migrateQuestCatalog(catalog: QuestCatalog, catalogPath: string): Promise<void> {
    const actors = Array.isArray(catalog.actors) ? catalog.actors : [];
    let changed = false;
    const updatedActors = await Promise.all(actors.map(async (actor) => {
      if (!this.hasLegacyQuestAvatar(actor)) {
        return actor;
      }
      const migratedPath = await this.migrateLegacyReference(actor.avatar_url || '');
      if (!migratedPath) {
        console.warn('Unable to migrate legacy quest avatar reference:', actor.avatar_url, 'in', catalogPath);
        return actor;
      }
      changed = true;
      return {
        ...actor,
        avatar_url: migratedPath,
      } as QuestActor;
    }));

    if (!changed) {
      return;
    }
    this.questsService.saveCatalog({
      ...catalog,
      actors: updatedActors,
    });
  }

  private hasLegacyCharacterAvatar(character: Character | null | undefined): boolean {
    return Boolean(character?.avatar && this.isLegacyReference(character.avatar));
  }

  private hasLegacyQuestAvatar(actor: QuestActor | null | undefined): boolean {
    return Boolean(actor?.avatar_url && this.isLegacyReference(actor.avatar_url));
  }

  private async migrateLegacyReference(reference: string): Promise<string | null> {
    if (!this.isLegacyReference(reference)) {
      return reference;
    }
    if (this.legacyReferenceMap.has(reference)) {
      return this.legacyReferenceMap.get(reference) || null;
    }

    const legacyId = reference.startsWith('avatar://')
      ? reference.slice('avatar://'.length)
      : reference;
    if (!legacyId) {
      return null;
    }
    if (this.legacyReferenceMap.has(legacyId)) {
      const existingPath = this.legacyReferenceMap.get(legacyId) || null;
      if (existingPath) {
        this.legacyReferenceMap.set(reference, existingPath);
      }
      return existingPath;
    }

    let migrationPromise = this.legacyMigrationPromises.get(legacyId);
    if (!migrationPromise) {
      migrationPromise = this.copyLegacyAvatarToFilesystem(legacyId);
      this.legacyMigrationPromises.set(legacyId, migrationPromise);
    }

    try {
      const migratedPath = await migrationPromise;
      if (migratedPath) {
        this.legacyReferenceMap.set(legacyId, migratedPath);
        this.legacyReferenceMap.set(`avatar://${legacyId}`, migratedPath);
        this.legacyReferenceMap.set(reference, migratedPath);
      }
      return migratedPath;
    } finally {
      this.legacyMigrationPromises.delete(legacyId);
    }
  }

  private async copyLegacyAvatarToFilesystem(legacyId: string): Promise<string | null> {
    const legacyAvatars = await this.getAllLegacyAvatars();
    const matchingAvatar = legacyAvatars.find((avatar) => avatar.id === legacyId);
    if (!matchingAvatar) {
      return null;
    }
    return this.avatarService.writeAvatarBlob(
      matchingAvatar.imageBlob,
      matchingAvatar.fileName,
      matchingAvatar.imageBlob.type || undefined,
    );
  }

  private isLegacyReference(reference: string | null | undefined): boolean {
    if (!reference) {
      return false;
    }
    if (reference.startsWith('avatar://')) {
      return true;
    }
    return !this.avatarService.isAbsoluteFilePath(reference) && !this.avatarService.isDirectUrl(reference);
  }

  private async getAllLegacyAvatars(): Promise<LegacyAvatarData[]> {
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
        const avatars = (request.result as LegacyAvatarData[]).map((avatar) => ({
          ...avatar,
          uploadTime: new Date(avatar.uploadTime),
        }));
        avatars.sort((a, b) => b.uploadTime.getTime() - a.uploadTime.getTime());
        resolve(avatars);
      };

      request.onerror = () => {
        reject(request.error);
      };
    });
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

  private async ensureDBReady(): Promise<void> {
    if (!this.db) {
      await this.initDB();
    }
  }
}
