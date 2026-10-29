import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { OidcSecurityService } from 'angular-auth-oidc-client';
import { MemberResponse } from '../../api/api-types';
import { fakeOidc } from '../../testing/fake-oidc';
import { filterMembers, MemberListPage } from './member-list';

function member(overrides: Partial<MemberResponse>): MemberResponse {
  return {
    id: crypto.randomUUID(),
    firstName: 'Erika',
    lastName: 'Muster',
    birthDate: '2012-03-04',
    gender: 'female',
    membershipType: 'active',
    entryDate: '2019-08-01',
    left: false,
    version: 0,
    ...overrides,
  };
}

describe('filterMembers', () => {
  const members = [
    member({ lastName: 'Zander', city: 'Wedel', memberNumber: '10' }),
    member({ lastName: 'Ahrens', city: 'Hamburg', memberNumber: '9' }),
    member({ lastName: 'Becker', left: true }),
  ];
  const byName = { active: 'name', direction: 'asc' } as const;

  it('zeigt standardmäßig nur aktuelle Mitglieder, nach Name sortiert', () => {
    const names = filterMembers(members, '', 'current', byName).map((m) => m.lastName);
    expect(names).toEqual(['Ahrens', 'Zander']);
  });

  it('filtert ausgetretene und sucht in Name, Nummer und Ort', () => {
    expect(filterMembers(members, '', 'left', byName).map((m) => m.lastName)).toEqual(['Becker']);
    expect(filterMembers(members, 'wedel', 'all', byName).map((m) => m.lastName)).toEqual([
      'Zander',
    ]);
  });

  it('sortiert Nummern numerisch und absteigend', () => {
    const sorted = filterMembers(members, '', 'current', {
      active: 'memberNumber',
      direction: 'desc',
    });
    expect(sorted.map((m) => m.memberNumber)).toEqual(['10', '9']);
  });
});

describe('MemberListPage', () => {
  let http: HttpTestingController;

  async function render(roles: string[]) {
    await TestBed.configureTestingModule({
      imports: [MemberListPage],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: OidcSecurityService, useValue: fakeOidc(true) },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(MemberListPage);
    TestBed.tick();
    http.expectOne('/api/me').flush({ subject: '1', displayName: 'X', email: null, roles });
    http.expectOne('/api/members').flush([member({ lastName: 'Ahrens', city: 'Hamburg' })]);
    await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }

  afterEach(() => http.verify());

  it('zeigt die Mitglieder und für Abteilungsleiter "Mitglied anlegen"', async () => {
    const element = await render(['member', 'department_head']);
    expect(element.textContent).toContain('Ahrens, Erika');
    expect(element.textContent).toContain('1 Mitglied');
    expect(element.textContent).toContain('Mitglied anlegen');
  });

  it('bietet dem Administrator kein Anlegen an', async () => {
    const element = await render(['admin']);
    expect(element.textContent).not.toContain('Mitglied anlegen');
  });
});
