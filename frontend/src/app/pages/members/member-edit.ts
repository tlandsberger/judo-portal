import { Component, computed, inject, input, linkedSignal, signal } from '@angular/core';
import { HttpClient, HttpErrorResponse, httpResource } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
import {
  apply,
  disabled,
  form,
  FormField,
  submit,
  type FieldTree,
  type ValidationError,
} from '@angular/forms/signals';
import { MatButton } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatError, MatFormField, MatHint, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatOption, MatSelect } from '@angular/material/select';
import { MatSnackBar } from '@angular/material/snack-bar';
import { firstValueFrom } from 'rxjs';
import { MemberResponse } from '../../api/api-types';
import { CurrentUser } from '../../auth/current-user';
import { ConfirmDialog, ConfirmDialogData } from '../../shared/confirm-dialog';
import { problemDetails } from '../../shared/problem-details';
import {
  emptyMember,
  isoDate,
  MEMBER_FIELDS,
  MemberField,
  MemberFormModel,
  memberSchema,
  toFormModel,
  toRequest,
} from './member-form';
import { MemberAccessSection } from './member-access';
import { GENDER_LABELS, MEMBERSHIP_LABELS } from './member-labels';

/** Mitglied anlegen (`/members/new`) oder anzeigen und bearbeiten (`/members/:id`). */
@Component({
  selector: 'judo-member-edit',
  imports: [
    RouterLink,
    FormField,
    MatButton,
    MatError,
    MatFormField,
    MatHint,
    MatInput,
    MatLabel,
    MatOption,
    MatProgressBar,
    MatSelect,
    MemberAccessSection,
  ],
  templateUrl: './member-edit.html',
  styleUrl: './member-edit.scss',
})
export class MemberEditPage {
  /** Aus der Route (`:id`); fehlt beim Anlegen. */
  readonly id = input<string>();

  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly snackBar = inject(MatSnackBar);
  private readonly dialog = inject(MatDialog);
  protected readonly permissions = inject(CurrentUser).permissions;

  private readonly today = isoDate(new Date());
  protected readonly genders = Object.entries(GENDER_LABELS);
  protected readonly membershipTypes = Object.entries(MEMBERSHIP_LABELS);

  protected readonly member = httpResource<MemberResponse>(() => {
    const id = this.id();
    return id ? `/api/members/${id}` : undefined;
  });
  protected readonly isNew = computed(() => !this.id());
  protected readonly notFound = computed(() => {
    const error = this.member.error();
    return error instanceof HttpErrorResponse && error.status === 404;
  });

  /** Formularstand; wird beim (Neu-)Laden des Mitglieds zurückgesetzt. */
  private readonly model = linkedSignal<MemberFormModel>(() =>
    this.member.hasValue() ? toFormModel(this.member.value()) : emptyMember(this.today),
  );
  protected readonly form = form(this.model, (member) => {
    apply(member, memberSchema(this.today));
    disabled(member, { when: () => !this.permissions().writeMembers });
  });

  protected readonly saving = signal(false);
  protected readonly saveError = signal<string | null>(null);
  protected readonly conflict = signal(false);

  protected title(): string {
    if (this.isNew()) {
      return 'Mitglied anlegen';
    }
    const { firstName, lastName } = this.member.hasValue()
      ? this.member.value()
      : { firstName: '', lastName: '' };
    return `${firstName} ${lastName}`;
  }

  protected errorText(field: FieldTree<unknown>): string {
    return field().errors()[0]?.message ?? '';
  }

  protected async save(): Promise<void> {
    this.saveError.set(null);
    this.conflict.set(false);
    await submit(this.form, async (member) => {
      const id = this.id();
      const version = this.member.hasValue() ? this.member.value().version : null;
      const request = toRequest(member().value(), version);
      this.saving.set(true);
      try {
        await firstValueFrom(
          id
            ? this.http.put<MemberResponse>(`/api/members/${id}`, request)
            : this.http.post<MemberResponse>('/api/members', request),
        );
      } catch (error) {
        return this.serverErrors(error, member);
      } finally {
        this.saving.set(false);
      }
      this.snackBar.open(id ? 'Änderungen gespeichert.' : 'Mitglied angelegt.', undefined, {
        duration: 4000,
      });
      await this.router.navigate(['/members']);
      return undefined;
    });
  }

  protected reload(): void {
    this.saveError.set(null);
    this.conflict.set(false);
    this.member.reload();
  }

  protected async remove(): Promise<void> {
    const id = this.id();
    if (!id) {
      return;
    }
    const data: ConfirmDialogData = {
      title: 'Mitglied löschen?',
      message: `${this.title()} wird endgültig gelöscht. Wer austritt, bekommt stattdessen ein Austrittsdatum.`,
      confirm: 'Löschen',
    };
    const confirmed = await firstValueFrom(this.dialog.open(ConfirmDialog, { data }).afterClosed());
    if (!confirmed) {
      return;
    }
    try {
      await firstValueFrom(this.http.delete(`/api/members/${id}`));
    } catch (error) {
      this.saveError.set(problemDetails(error).detail ?? 'Löschen fehlgeschlagen.');
      return;
    }
    this.snackBar.open('Mitglied gelöscht.', undefined, { duration: 4000 });
    await this.router.navigate(['/members']);
  }

  /** Feldfehler des Backends an die Felder hängen, alles andere oberhalb der Buttons zeigen. */
  private serverErrors(
    error: unknown,
    member: FieldTree<MemberFormModel>,
  ): ValidationError.WithOptionalFieldTree[] {
    const problem = problemDetails(error);
    const fieldErrors = (problem.errors ?? [])
      .filter((e) => MEMBER_FIELDS.includes(e.field as MemberField))
      .map((e) => ({
        kind: 'server',
        message: e.message,
        fieldTree: member[e.field as MemberField],
      }));
    if (fieldErrors.length === 0) {
      this.conflict.set(error instanceof HttpErrorResponse && error.status === 409);
      this.saveError.set(
        problem.detail ?? 'Speichern fehlgeschlagen. Bitte später erneut versuchen.',
      );
    }
    return fieldErrors;
  }
}
