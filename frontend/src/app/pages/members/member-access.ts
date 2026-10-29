import { Component, computed, inject, input, signal } from '@angular/core';
import { HttpClient, httpResource } from '@angular/common/http';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { firstValueFrom } from 'rxjs';
import { AccessRelation, InvitationResponse, MemberAccessResponse } from '../../api/api-types';
import { ConfirmDialog, ConfirmDialogData } from '../../shared/confirm-dialog';
import { problemDetails } from '../../shared/problem-details';
import { ageOn, RELATION_LABELS, STATUS_LABELS } from './access-labels';
import { InviteDialog, InviteDialogData } from './invite-dialog';

/**
 * Zugänge eines Mitglieds (Abteilungsleiter, Administrator): eigener Zugang ab 14, Erziehungsberechtigte
 * für Minderjährige. Die Regeln prüft verbindlich das Backend, hier steuern sie nur die Buttons.
 */
@Component({
  selector: 'judo-member-access',
  imports: [MatButton, MatProgressBar],
  template: `
    <section aria-labelledby="access-title">
      <h2 id="access-title">Zugänge zum Portal</h2>
      @if (accesses.isLoading()) {
        <mat-progress-bar mode="indeterminate" aria-label="Zugänge werden geladen" />
      } @else if (accesses.error()) {
        <p class="error" role="alert">
          Die Zugänge konnten nicht geladen werden.
          <button matButton type="button" (click)="accesses.reload()">Erneut versuchen</button>
        </p>
      } @else {
        @for (access of list(); track access.id) {
          <div class="access">
            <div class="who">
              <strong>{{ access.name }}</strong>
              <span class="email">{{ access.email }}</span>
            </div>
            <span class="tag">{{ relationLabel(access.relation) }}</span>
            <span class="tag" [class.warn]="access.status !== 'active'">{{
              statusLabel(access)
            }}</span>
            <span class="spacer"></span>
            @if (access.status === 'invited') {
              <button matButton type="button" [disabled]="busy()" (click)="resend(access)">
                Erneut senden
              </button>
            }
            <button
              matButton
              type="button"
              class="danger"
              [disabled]="busy()"
              (click)="remove(access)"
            >
              Entfernen
            </button>
          </div>
        } @empty {
          <p class="hint">Noch kein Zugang. {{ memberName() }} sieht das Portal bisher nicht.</p>
        }
        <div class="actions">
          @if (canInviteSelf()) {
            <button matButton="outlined" type="button" (click)="invite('self')">
              Eigenen Zugang einladen
            </button>
          }
          @if (canInviteGuardian()) {
            <button matButton="outlined" type="button" (click)="invite('guardian')">
              Erziehungsberechtigte einladen
            </button>
          }
        </div>
        @if (!canInviteSelf() && age() < 14) {
          <p class="hint">Einen eigenen Zugang gibt es ab 14 Jahren.</p>
        }
      }
    </section>
  `,
  styles: `
    h2 {
      font: var(--mat-sys-title-large);
      margin: 32px 0 8px;
    }
    .access {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 12px;
      padding: 8px 0;
      border-bottom: 1px solid var(--mat-sys-outline-variant);
    }
    .who {
      display: flex;
      flex-direction: column;
      min-width: 200px;
    }
    .email,
    .hint {
      color: var(--mat-sys-on-surface-variant);
    }
    .tag {
      padding: 2px 8px;
      border-radius: var(--mat-sys-corner-small);
      font: var(--mat-sys-label-medium);
      background: var(--mat-sys-secondary-container);
      color: var(--mat-sys-on-secondary-container);
    }
    .tag.warn {
      background: var(--mat-sys-surface-container-highest);
      color: var(--mat-sys-on-surface-variant);
    }
    .spacer {
      flex: 1;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .danger,
    .error {
      color: var(--mat-sys-error);
    }
  `,
})
export class MemberAccessSection {
  readonly memberId = input.required<string>();
  readonly memberName = input.required<string>();
  readonly birthDate = input.required<string>();

  private readonly http = inject(HttpClient);
  private readonly dialog = inject(MatDialog);
  private readonly snackBar = inject(MatSnackBar);

  protected readonly accesses = httpResource<MemberAccessResponse[]>(
    () => `/api/members/${this.memberId()}/access`,
    { defaultValue: [] },
  );
  protected readonly list = computed(() => (this.accesses.hasValue() ? this.accesses.value() : []));
  protected readonly busy = signal(false);
  protected readonly age = computed(() => ageOn(this.birthDate(), new Date()));
  protected readonly canInviteSelf = computed(
    () => this.age() >= 14 && !this.list().some((a) => a.relation === 'self'),
  );
  protected readonly canInviteGuardian = computed(() => this.age() < 18);

  protected relationLabel(relation: AccessRelation): string {
    return RELATION_LABELS[relation];
  }

  protected statusLabel(access: MemberAccessResponse): string {
    return STATUS_LABELS[access.status];
  }

  protected async invite(relation: AccessRelation): Promise<void> {
    const data: InviteDialogData = {
      memberId: this.memberId(),
      memberName: this.memberName(),
      relation,
    };
    const result = await firstValueFrom(
      this.dialog
        .open<InviteDialog, InviteDialogData, InvitationResponse>(InviteDialog, {
          data,
          width: '480px',
        })
        .afterClosed(),
    );
    if (!result) {
      return;
    }
    this.snackBar.open(
      result.invitationSent
        ? `Einladung an ${result.access.email} gesendet.`
        : `Bestehendes Konto ${result.access.email} verknüpft – keine neue E-Mail nötig.`,
      undefined,
      { duration: 6000 },
    );
    this.accesses.reload();
  }

  protected async resend(access: MemberAccessResponse): Promise<void> {
    await this.run(
      this.http.post(`/api/members/${this.memberId()}/access/${access.id}/resend`, null),
      `Einladung an ${access.email} erneut gesendet.`,
    );
  }

  protected async remove(access: MemberAccessResponse): Promise<void> {
    const data: ConfirmDialogData = {
      title: 'Zugang entfernen?',
      message: `${access.name} sieht die Daten von ${this.memberName()} danach nicht mehr. Das Konto selbst bleibt bestehen.`,
      confirm: 'Entfernen',
    };
    const confirmed = await firstValueFrom(this.dialog.open(ConfirmDialog, { data }).afterClosed());
    if (confirmed) {
      await this.run(
        this.http.delete(`/api/members/${this.memberId()}/access/${access.id}`),
        'Zugang entfernt.',
      );
    }
  }

  private async run(request: ReturnType<HttpClient['delete']>, success: string): Promise<void> {
    this.busy.set(true);
    try {
      await firstValueFrom(request);
      this.snackBar.open(success, undefined, { duration: 4000 });
      this.accesses.reload();
    } catch (error) {
      this.snackBar.open(problemDetails(error).detail ?? 'Das hat nicht geklappt.', undefined, {
        duration: 6000,
      });
    } finally {
      this.busy.set(false);
    }
  }
}
