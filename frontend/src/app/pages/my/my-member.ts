import { Component, computed, input } from '@angular/core';
import { DatePipe } from '@angular/common';
import { HttpErrorResponse, httpResource } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { MatButton } from '@angular/material/button';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MyMemberResponse } from '../../api/api-types';
import { GENDER_LABELS, MEMBERSHIP_LABELS } from '../members/member-labels';

/** Eigene Daten bzw. die des Kindes, nur lesend (`/my/members/:id`). */
@Component({
  selector: 'judo-my-member',
  imports: [DatePipe, RouterLink, MatButton, MatProgressBar],
  template: `
    <a matButton routerLink="/home" class="back">Zur Startseite</a>
    @if (data.isLoading()) {
      <mat-progress-bar mode="indeterminate" aria-label="Daten werden geladen" />
    } @else if (notFound()) {
      <p role="alert">Diese Daten gibt es nicht oder du darfst sie nicht sehen.</p>
    } @else if (data.error()) {
      <p role="alert">Die Daten konnten nicht geladen werden.</p>
    } @else if (data.value(); as entry) {
      <h1>{{ entry.member.firstName }} {{ entry.member.lastName }}</h1>
      <p class="hint">
        Änderungen bitte an die Abteilungsleitung melden – hier kannst du die Daten nur ansehen.
      </p>
      <dl>
        <dt>Geburtsdatum</dt>
        <dd>{{ entry.member.birthDate | date: 'dd.MM.yyyy' }}</dd>
        <dt>Geschlecht</dt>
        <dd>{{ entry.member.gender ? genders[entry.member.gender] : '–' }}</dd>
        <dt>Adresse</dt>
        <dd>
          @if (entry.member.street) {
            <div>{{ entry.member.street }}</div>
          }
          @if (entry.member.postalCode || entry.member.city) {
            <div>{{ entry.member.postalCode }} {{ entry.member.city }}</div>
          }
          @if (!entry.member.street && !entry.member.postalCode && !entry.member.city) {
            –
          }
        </dd>
        <dt>Telefon</dt>
        <dd>{{ entry.member.phone || '–' }}</dd>
        <dt>E-Mail</dt>
        <dd>{{ entry.member.email || '–' }}</dd>
        <dt>Mitgliedsnummer</dt>
        <dd>{{ entry.member.memberNumber || '–' }}</dd>
        <dt>Mitgliedschaft</dt>
        <dd>{{ memberships[entry.member.membershipType] }}</dd>
        <dt>Eintritt</dt>
        <dd>{{ entry.member.entryDate | date: 'dd.MM.yyyy' }}</dd>
        @if (entry.member.exitDate) {
          <dt>Austritt</dt>
          <dd>{{ entry.member.exitDate | date: 'dd.MM.yyyy' }}</dd>
        }
      </dl>
    }
  `,
  styles: `
    .back {
      margin-bottom: 8px;
    }
    h1 {
      font: var(--mat-sys-headline-medium);
      margin: 0 0 8px;
    }
    .hint {
      color: var(--mat-sys-on-surface-variant);
    }
    dl {
      display: grid;
      grid-template-columns: minmax(120px, max-content) 1fr;
      gap: 8px 24px;
      margin: 24px 0;
    }
    dt {
      color: var(--mat-sys-on-surface-variant);
    }
    dd {
      margin: 0;
    }
  `,
})
export class MyMemberPage {
  /** Aus der Route (`:id`). */
  readonly id = input.required<string>();

  protected readonly data = httpResource<MyMemberResponse>(() => `/api/me/members/${this.id()}`);
  protected readonly notFound = computed(() => {
    const error = this.data.error();
    return error instanceof HttpErrorResponse && error.status === 404;
  });
  protected readonly genders = GENDER_LABELS;
  protected readonly memberships = MEMBERSHIP_LABELS;
}
