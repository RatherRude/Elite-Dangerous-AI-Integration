import { Injectable } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { Observable } from 'rxjs';
import { ConfirmationDialogComponent, ConfirmationDialogData } from '../components/confirmation-dialog/confirmation-dialog.component';

@Injectable({
  providedIn: 'root'
})
export class ConfirmationDialogService {
  constructor(private dialog: MatDialog) {}

  /**
   * Opens a confirmation dialog with the provided data
   * @param data The dialog configuration data
   * @returns An Observable that resolves to true when confirmed or false when cancelled
   */
  openConfirmationDialog(data: ConfirmationDialogData): Observable<boolean> {
    const dialogRef = this.dialog.open(ConfirmationDialogComponent, {
      width: 'auto',
      disableClose: true,
      data
    });

    return dialogRef.afterClosed();
  }
} 