import { Component, OnInit, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogRef, MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatSnackBar } from '@angular/material/snack-bar';
import { AvatarService, AvatarData } from '../../services/avatar.service';
import { MatTooltipModule } from '@angular/material/tooltip';

export interface AvatarCatalogDialogData {
  currentAvatarId?: string;
}

export interface AvatarCatalogResult {
  avatarId: string;
}

@Component({
  selector: 'app-avatar-catalog-dialog',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatTooltipModule
  ],
  templateUrl: './avatar-catalog-dialog.component.html',
  styleUrl: './avatar-catalog-dialog.component.scss'
})
export class AvatarCatalogDialogComponent implements OnInit {
  avatars: AvatarData[] = [];
  avatarUrls: Map<string, string> = new Map();
  uploading = false;

  constructor(
    public dialogRef: MatDialogRef<AvatarCatalogDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: AvatarCatalogDialogData,
    private avatarService: AvatarService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit() {
    this.loadAvatars();
  }

  async loadAvatars() {
    try {
      this.avatars = await this.avatarService.getAllAvatars();
      
      // Generate URLs for all avatars
      for (const avatar of this.avatars) {
        const url = await this.avatarService.getAvatar(avatar.id);
        if (url) {
          this.avatarUrls.set(avatar.id, url);
        }
      }
    } catch (error) {
      console.error('Error loading avatars:', error);
      this.snackBar.open('Error loading avatars', 'Dismiss', { duration: 3000 });
    }
  }

  onFileSelected(event: any) {
    const file = event.target.files?.[0];
    if (file) {
      this.uploadAvatar(file);
    }
  }

  async uploadAvatar(file: File) {
    if (!file.type.startsWith('image/')) {
      this.snackBar.open('Please select an image file', 'Dismiss', { duration: 3000 });
      return;
    }

    if (file.size > 50 * 1024 * 1024) { // 50MB limit
      this.snackBar.open('Image size must be less than 50MB', 'Dismiss', { duration: 3000 });
      return;
    }

    // Check aspect ratio
    try {
      const hasSquareAspectRatio = await this.checkImageAspectRatio(file);
      if (!hasSquareAspectRatio) {
        this.snackBar.open('Image must have a 1:1 aspect ratio (square)', 'Dismiss', { duration: 3000 });
        return;
      }
    } catch (error) {
      console.error('Error checking image dimensions:', error);
      this.snackBar.open('Error validating image', 'Dismiss', { duration: 3000 });
      return;
    }

    this.uploading = true;
    try {
      const avatarId = await this.avatarService.uploadAvatar(file);
      this.snackBar.open('Avatar uploaded successfully', 'Dismiss', { duration: 3000 });
      await this.loadAvatars(); // Refresh the list
    } catch (error) {
      console.error('Error uploading avatar:', error);
      this.snackBar.open('Error uploading avatar', 'Dismiss', { duration: 3000 });
    } finally {
      this.uploading = false;
    }
  }

  private checkImageAspectRatio(file: File): Promise<boolean> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      
      img.onload = () => {
        URL.revokeObjectURL(img.src); // Clean up
        resolve(img.width === img.height);
      };
      
      img.onerror = () => {
        URL.revokeObjectURL(img.src); // Clean up
        reject(new Error('Failed to load image'));
      };
      
      img.src = URL.createObjectURL(file);
    });
  }

  selectAvatar(avatarId: string) {
    this.dialogRef.close({ avatarId } as AvatarCatalogResult);
  }

  async deleteAvatar(avatarId: string) {
    try {
      await this.avatarService.deleteAvatar(avatarId);
      this.snackBar.open('Avatar deleted', 'Dismiss', { duration: 3000 });
      
      // Clean up URL
      const url = this.avatarUrls.get(avatarId);
      if (url) {
        URL.revokeObjectURL(url);
        this.avatarUrls.delete(avatarId);
      }
      
      await this.loadAvatars(); // Refresh the list
    } catch (error) {
      console.error('Error deleting avatar:', error);
      this.snackBar.open('Error deleting avatar', 'Dismiss', { duration: 3000 });
    }
  }

  getAvatarUrl(avatarId: string): string | null {
    return this.avatarUrls.get(avatarId) || null;
  }

  formatUploadTime(uploadTime: Date): string {
    return new Date(uploadTime).toLocaleString();
  }

  onCancel() {
    this.dialogRef.close();
  }

  ngOnDestroy() {
    // Clean up all object URLs
    this.avatarUrls.forEach(url => URL.revokeObjectURL(url));
    this.avatarUrls.clear();
  }
} 