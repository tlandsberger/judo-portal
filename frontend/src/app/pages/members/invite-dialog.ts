import { Component, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import {
  email,
  form,
  FormField,
  maxLength,
  required,
  submit,
  type FieldTree,
} from '@angular/forms/signals';
import { MatButton } from '@angular/material/button';
import {
  MAT_DIALOG_DATA,
  MatDialogActions,
  MatDialogClose,
  MatDialogContent,
  MatDialogRef,
  MatDialogTitle,
} from '@angular/material/dialog';
import { MatError, MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { firstValueFrom } from 'rxjs';
import { AccessRelation, InvitationRequest, InvitationResponse } from '../../api/api-types';
import { provideFormDefaults } from '../../shared/form-defaults';
import { problemDetails } from '../../shared/problem-details';

export interface InviteDialogData {
  memberId: string;
  memberName: string;
  relation: AccessRelation;
}

interface InviteForm {
  email: string;
  firstName: string;
  lastName: string;
}

/** Einladung per E-Mail; liefert beim Schließen die `InvitationResponse` (oder nichts bei Abbruch). */
@Component({
  selector: 'judo-invite-dialog',
  // Dialoge hängen nicht im Injector der Route, daher die Formular-Defaults hier noch einmal.
  providers: [provideFormDefaults()],
  imports: [
    FormField,
    MatButton,
    MatDialogActions,
    MatDialogClose,
    MatDialogContent,
    MatDialogTitle,
    MatError,
    MatFormField,
    MatInput,
    MatLabel,
  ],
  template: `
    <h2 mat-dialog-title>
      {{ guardian ? 'Erziehungsberechtigte einladen' : 'Eigenen Zugang einladen' }}
    </h2>
    <form novalidate (submit)="$event.preventDefault(); send()">
      <mat-dialog-content>
        <p class="intro">
          @if (guardian) {
            Die Person bekommt eine E-Mail zum Festlegen ihres Passworts und sieht danach die Daten
            von {{ data.memberName }}, bis das Kind volljährig ist.
          } @else {
            {{ data.memberName }} bekommt eine E-Mail zum Festlegen des Passworts und sieht danach
            die eigenen Daten.
          }
        </p>
        <mat-form-field>
          <mat-label>E-Mail</mat-label>
          <input matInput type="email" [formField]="invite.email" autocomplete="off" />
          <mat-error>{{ errorText(invite.email) }}</mat-error>
        </mat-form-field>
        @if (guardian) {
          <mat-form-field>
            <mat-label>Vorname</mat-label>
            <input matInput [formField]="invite.firstName" autocomplete="off" />
            <mat-error>{{ errorText(invite.firstName) }}</mat-error>
          </mat-form-field>
          <mat-form-field>
            <mat-label>Nachname</mat-label>
            <input matInput [formField]="invite.lastName" autocomplete="off" />
            <mat-error>{{ errorText(invite.lastName) }}</mat-error>
          </mat-form-field>
        }
        @if (error(); as message) {
          <p class="error" role="alert">{{ message }}</p>
        }
      </mat-dialog-content>
      <mat-dialog-actions align="end">
        <button matButton type="button" mat-dialog-close>Abbrechen</button>
        <button matButton="filled" type="submit" [disabled]="sending()">Einladen</button>
      </mat-dialog-actions>
    </form>
  `,
  styles: `
    mat-form-field {
      display: block;
    }
    .intro {
      margin-top: 0;
    }
    .error {
      color: var(--mat-sys-error);
    }
  `,
})
export class InviteDialog {
  protected readonly data = inject<InviteDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<InviteDialog, InvitationResponse>);
  private readonly http = inject(HttpClient);

  protected readonly guardian = this.data.relation === 'guardian';
  protected readonly sending = signal(false);
  protected readonly error = signal<string | null>(null);

  private readonly model = signal<InviteForm>({ email: '', firstName: '', lastName: '' });
  protected readonly invite = form(this.model, (invite) => {
    required(invite.email, { message: 'Bitte die E-Mail-Adresse angeben.' });
    email(invite.email, { message: 'Bitte eine gültige E-Mail-Adresse angeben.' });
    maxLength(invite.email, 254, { message: 'Höchstens 254 Zeichen.' });
    required(invite.firstName, {
      message: 'Bitte den Vornamen angeben.',
      when: () => this.guardian,
    });
    required(invite.lastName, {
      message: 'Bitte den Nachnamen angeben.',
      when: () => this.guardian,
    });
    maxLength(invite.firstName, 100, { message: 'Höchstens 100 Zeichen.' });
    maxLength(invite.lastName, 100, { message: 'Höchstens 100 Zeichen.' });
  });

  protected errorText(field: FieldTree<unknown>): string {
    return field().errors()[0]?.message ?? '';
  }

  protected async send(): Promise<void> {
    this.error.set(null);
    await submit(this.invite, async (invite) => {
      const value = invite().value();
      const request: InvitationRequest = {
        relation: this.data.relation,
        email: value.email.trim(),
        firstName: this.guardian ? value.firstName.trim() : null,
        lastName: this.guardian ? value.lastName.trim() : null,
      };
      this.sending.set(true);
      try {
        const response = await firstValueFrom(
          this.http.post<InvitationResponse>(`/api/members/${this.data.memberId}/access`, request),
        );
        this.dialogRef.close(response);
        return undefined;
      } catch (error) {
        const problem = problemDetails(error);
        const fieldError = problem.errors?.find((e) =>
          ['email', 'firstName', 'lastName'].includes(e.field),
        );
        if (fieldError) {
          return {
            kind: 'server',
            message: fieldError.message,
            fieldTree: invite[fieldError.field as keyof InviteForm],
          };
        }
        this.error.set(
          problem.errors?.[0]?.message ??
            problem.detail ??
            'Die Einladung ist fehlgeschlagen. Bitte später erneut versuchen.',
        );
        return undefined;
      } finally {
        this.sending.set(false);
      }
    });
  }
}
