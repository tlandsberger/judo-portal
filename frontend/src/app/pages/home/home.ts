import { Component, computed, inject } from '@angular/core';
import { HttpErrorResponse, httpResource } from '@angular/common/http';
import { MatButton } from '@angular/material/button';
import { MatChip, MatChipSet } from '@angular/material/chips';
import { MatProgressBar } from '@angular/material/progress-bar';
import { OidcSecurityService } from 'angular-auth-oidc-client';
import { MeResponse } from '../../api/api-types';
import { roleLabel } from '../../shared/role-labels';

/** Startseite nach dem Login: zeigt den angemeldeten Benutzer aus GET /api/me. */
@Component({
  selector: 'judo-home',
  imports: [MatButton, MatChipSet, MatChip, MatProgressBar],
  template: `
    @if (me.isLoading()) {
      <mat-progress-bar mode="indeterminate" aria-label="Daten werden geladen" />
    } @else if (sessionExpired()) {
      <section class="message" role="alert">
        <p>Deine Sitzung ist abgelaufen.</p>
        <button matButton="filled" type="button" (click)="login()">Neu anmelden</button>
      </section>
    } @else if (me.error()) {
      <section class="message" role="alert">
        <p>Die Daten konnten nicht geladen werden.</p>
        <button matButton="outlined" type="button" (click)="me.reload()">Erneut versuchen</button>
      </section>
    } @else if (me.value(); as user) {
      <h1>Hallo {{ user.displayName }}</h1>
      @if (user.email) {
        <p class="email">{{ user.email }}</p>
      }
      <h2>Deine Rollen</h2>
      <mat-chip-set aria-label="Deine Rollen">
        @for (role of user.roles; track role) {
          <mat-chip>{{ label(role) }}</mat-chip>
        } @empty {
          <p>Dir ist noch keine Rolle zugewiesen.</p>
        }
      </mat-chip-set>
    }
  `,
  styles: `
    h1 {
      font: var(--mat-sys-headline-medium);
      margin: 0 0 4px;
    }
    h2 {
      font: var(--mat-sys-title-medium);
      margin: 24px 0 8px;
    }
    .email {
      color: var(--mat-sys-on-surface-variant);
      margin: 0;
    }
    .message {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 12px;
    }
  `,
})
export class HomePage {
  private readonly oidc = inject(OidcSecurityService);

  protected readonly me = httpResource<MeResponse>(() => '/api/me');
  protected readonly sessionExpired = computed(() => {
    const error = this.me.error();
    return error instanceof HttpErrorResponse && error.status === 401;
  });
  protected readonly label = roleLabel;

  protected login(): void {
    this.oidc.authorize();
  }
}
