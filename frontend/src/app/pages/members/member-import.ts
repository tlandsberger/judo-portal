import { Component, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
import { MatButton } from '@angular/material/button';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { firstValueFrom } from 'rxjs';
import { ImportAction, ImportResponse, ImportRow } from '../../api/api-types';
import { problemDetails } from '../../shared/problem-details';

const ACTION_LABELS: Record<ImportAction, string> = {
  create: 'Neu',
  update: 'Geändert',
  unchanged: 'Unverändert',
  error: 'Fehler',
};

/**
 * CSV-Import der bisherigen Mitgliederliste: Datei wählen → Vorschau → Import ausführen.
 * Die Vorschau speichert nichts; beim Ausführen wertet das Backend dieselbe Datei erneut aus.
 */
@Component({
  selector: 'judo-member-import',
  imports: [RouterLink, MatButton, MatProgressBar, MatTableModule],
  templateUrl: './member-import.html',
  styleUrl: './member-import.scss',
})
export class MemberImportPage {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly file = signal<File | null>(null);
  protected readonly preview = signal<ImportResponse | null>(null);
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly importable = computed(() => {
    const preview = this.preview();
    return preview ? preview.created + preview.updated : 0;
  });

  protected readonly columns = ['line', 'memberNumber', 'name', 'action', 'details'];

  protected actionLabel(row: ImportRow): string {
    return ACTION_LABELS[row.action];
  }

  protected async choose(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    input.value = '';
    if (!file) {
      return;
    }
    this.file.set(file);
    this.preview.set(null);
    this.preview.set(await this.upload('/api/members/import/preview', file));
  }

  protected async execute(): Promise<void> {
    const file = this.file();
    if (!file) {
      return;
    }
    const result = await this.upload('/api/members/import', file);
    if (!result) {
      return;
    }
    this.snackBar.open(
      `Import abgeschlossen: ${result.created} neu, ${result.updated} aktualisiert.`,
      undefined,
      { duration: 6000 },
    );
    await this.router.navigate(['/members']);
  }

  private async upload(url: string, file: File): Promise<ImportResponse | null> {
    const body = new FormData();
    body.append('file', file);
    this.busy.set(true);
    this.error.set(null);
    try {
      return await firstValueFrom(this.http.post<ImportResponse>(url, body));
    } catch (error) {
      const problem = problemDetails(error);
      this.error.set(
        problem.errors?.[0]?.message ??
          problem.detail ??
          'Die Datei konnte nicht verarbeitet werden. Bitte später erneut versuchen.',
      );
      return null;
    } finally {
      this.busy.set(false);
    }
  }
}
