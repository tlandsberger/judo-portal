import { Component, computed } from '@angular/core';
import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { MatButton } from '@angular/material/button';
import { MyMemberResponse } from '../../api/api-types';

/** „Meine Mitgliedschaft“ und „Meine Kinder“ auf der Startseite (nur lesend). */
@Component({
  selector: 'judo-my-members',
  imports: [DatePipe, RouterLink, MatButton],
  template: `
    @if (own(); as mine) {
      <h2>Meine Mitgliedschaft</h2>
      <ul class="cards">
        <li class="card">
          <strong>{{ mine.member.firstName }} {{ mine.member.lastName }}</strong>
          <span class="meta">Mitglied seit {{ mine.member.entryDate | date: 'dd.MM.yyyy' }}</span>
          <a matButton [routerLink]="['/my/members', mine.member.id]">Meine Daten ansehen</a>
        </li>
      </ul>
    }
    @if (children().length) {
      <h2>{{ children().length === 1 ? 'Mein Kind' : 'Meine Kinder' }}</h2>
      <ul class="cards">
        @for (child of children(); track child.member.id) {
          <li class="card">
            <strong>{{ child.member.firstName }} {{ child.member.lastName }}</strong>
            <span class="meta">geboren {{ child.member.birthDate | date: 'dd.MM.yyyy' }}</span>
            <a
              matButton
              [routerLink]="['/my/members', child.member.id]"
              [attr.aria-label]="'Daten von ' + child.member.firstName + ' ansehen'"
              >Daten ansehen</a
            >
          </li>
        }
      </ul>
    }
    @if (members.error()) {
      <p class="hint" role="alert">Deine Mitgliedsdaten konnten nicht geladen werden.</p>
    }
  `,
  styles: `
    h2 {
      font: var(--mat-sys-title-medium);
      margin: 24px 0 8px;
    }
    .cards {
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
      gap: 12px;
    }
    .card {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
      padding: 16px;
      border-radius: var(--mat-sys-corner-medium);
      background: var(--mat-sys-surface-container);
    }
    .meta,
    .hint {
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class MyMembersSection {
  protected readonly members = httpResource<MyMemberResponse[]>(() => '/api/me/members', {
    defaultValue: [],
  });
  private readonly list = computed(() => (this.members.hasValue() ? this.members.value() : []));
  protected readonly own = computed(() => this.list().find((m) => m.relation === 'self'));
  protected readonly children = computed(() =>
    this.list().filter((m) => m.relation === 'guardian'),
  );
}
