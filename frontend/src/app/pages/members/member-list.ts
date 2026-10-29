import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
import { MatButton } from '@angular/material/button';
import { MatButtonToggle, MatButtonToggleGroup } from '@angular/material/button-toggle';
import { MatFormField, MatLabel } from '@angular/material/form-field';
import { MatInput } from '@angular/material/input';
import { MatProgressBar } from '@angular/material/progress-bar';
import { MatSort, MatSortHeader, Sort } from '@angular/material/sort';
import { MatTableModule } from '@angular/material/table';
import { MemberResponse } from '../../api/api-types';
import { CurrentUser } from '../../auth/current-user';
import { MEMBERSHIP_LABELS } from './member-labels';

export type StatusFilter = 'current' | 'left' | 'all';

/** Mitglieder nach Status und Suchbegriff filtern und sortieren (rein, für Tests exportiert). */
export function filterMembers(
  members: readonly MemberResponse[],
  query: string,
  status: StatusFilter,
  sort: Sort,
): MemberResponse[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const matches = (m: MemberResponse) => {
    const text = [m.firstName, m.lastName, m.memberNumber, m.city].join(' ').toLowerCase();
    return words.every((word) => text.includes(word));
  };
  const keys: Record<string, (m: MemberResponse) => string> = {
    name: (m) => `${m.lastName} ${m.firstName}`,
    memberNumber: (m) => m.memberNumber ?? '',
    birthDate: (m) => m.birthDate,
    city: (m) => m.city ?? '',
  };
  const key = keys[sort.active] ?? keys['name'];
  const direction = sort.direction === 'desc' ? -1 : 1;
  return members
    .filter((m) => status === 'all' || (status === 'left') === m.left)
    .filter(matches)
    .sort(
      (a, b) =>
        direction * key(a).localeCompare(key(b), 'de', { numeric: true, sensitivity: 'base' }),
    );
}

/** Mitgliederliste für Vorstand, Kasse und Administration. */
@Component({
  selector: 'judo-member-list',
  imports: [
    DatePipe,
    RouterLink,
    MatButton,
    MatButtonToggle,
    MatButtonToggleGroup,
    MatFormField,
    MatInput,
    MatLabel,
    MatProgressBar,
    MatSort,
    MatSortHeader,
    MatTableModule,
  ],
  templateUrl: './member-list.html',
  styleUrl: './member-list.scss',
})
export class MemberListPage {
  private readonly router = inject(Router);
  protected readonly permissions = inject(CurrentUser).permissions;

  protected readonly members = httpResource<MemberResponse[]>(() => '/api/members', {
    defaultValue: [],
  });
  protected readonly query = signal('');
  protected readonly status = signal<StatusFilter>('current');
  protected readonly sort = signal<Sort>({ active: 'name', direction: 'asc' });
  protected readonly rows = computed(() =>
    filterMembers(
      this.members.hasValue() ? this.members.value() : [],
      this.query(),
      this.status(),
      this.sort(),
    ),
  );

  protected readonly columns = ['memberNumber', 'name', 'birthDate', 'city', 'membershipType'];

  protected membershipLabel(member: MemberResponse): string {
    return MEMBERSHIP_LABELS[member.membershipType];
  }

  protected search(event: Event): void {
    this.query.set((event.target as HTMLInputElement).value);
  }

  protected open(member: MemberResponse): void {
    void this.router.navigate(['/members', member.id]);
  }
}
