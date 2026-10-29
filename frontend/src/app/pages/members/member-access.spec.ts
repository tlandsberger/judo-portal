import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MatDialog } from '@angular/material/dialog';
import { of } from 'rxjs';
import { InvitationResponse, MemberAccessResponse } from '../../api/api-types';
import { ageOn } from './access-labels';
import { MemberAccessSection } from './member-access';

const MOTHER: MemberAccessResponse = {
  id: 'a-1',
  relation: 'guardian',
  email: 'mutter@example.org',
  name: 'Maria Muster',
  status: 'invited',
  createdAt: '2026-10-01T10:00:00Z',
};

function yearsAgo(years: number): string {
  const date = new Date();
  date.setFullYear(date.getFullYear() - years);
  return date.toISOString().slice(0, 10);
}

describe('ageOn', () => {
  it('zählt volle Jahre ab dem Geburtstag', () => {
    const today = new Date(2026, 9, 29);
    expect(ageOn('2012-10-29', today)).toBe(14);
    expect(ageOn('2012-10-30', today)).toBe(13);
  });
});

describe('MemberAccessSection', () => {
  let http: HttpTestingController;
  const dialog = { open: vi.fn() };

  async function render(birthDate: string, accesses: MemberAccessResponse[]) {
    await TestBed.configureTestingModule({
      imports: [MemberAccessSection],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: MatDialog, useValue: dialog },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(MemberAccessSection);
    fixture.componentRef.setInput('memberId', 'm-1');
    fixture.componentRef.setInput('memberName', 'Lena Ahrens');
    fixture.componentRef.setInput('birthDate', birthDate);
    TestBed.tick();
    http.expectOne('/api/members/m-1/access').flush(accesses);
    await fixture.whenStable();
    return fixture;
  }

  const text = (fixture: { nativeElement: unknown }) =>
    (fixture.nativeElement as HTMLElement).textContent ?? '';
  const button = (fixture: { nativeElement: unknown }, label: string) =>
    [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find((b) =>
      b.textContent?.includes(label),
    );

  /** Wartet auf Dialog-Promise und Request, ohne auf offene httpResource-Requests zu warten. */
  const settle = async () => {
    await new Promise((resolve) => setTimeout(resolve));
    TestBed.tick();
  };

  afterEach(() => {
    http.verify();
    dialog.open.mockReset();
  });

  it('zeigt Zugänge mit Status und bietet bei Kindern unter 14 nur Eltern an', async () => {
    const fixture = await render(yearsAgo(10), [MOTHER]);
    expect(text(fixture)).toContain('Maria Muster');
    expect(text(fixture)).toContain('Erziehungsberechtigt');
    expect(text(fixture)).toContain('Eingeladen');
    expect(button(fixture, 'Erneut senden')).toBeTruthy();
    expect(button(fixture, 'Erziehungsberechtigte einladen')).toBeTruthy();
    expect(button(fixture, 'Eigenen Zugang einladen')).toBeFalsy();
    expect(text(fixture)).toContain('ab 14 Jahren');
  });

  it('bietet Erwachsenen nur den eigenen Zugang an', async () => {
    const fixture = await render(yearsAgo(30), []);
    expect(button(fixture, 'Eigenen Zugang einladen')).toBeTruthy();
    expect(button(fixture, 'Erziehungsberechtigte einladen')).toBeFalsy();
  });

  it('lädt die Liste nach einer Einladung neu', async () => {
    const fixture = await render(yearsAgo(15), []);
    const response: InvitationResponse = {
      access: { ...MOTHER, relation: 'self', email: 'lena@example.org' },
      invitationSent: true,
    };
    dialog.open.mockReturnValue({ afterClosed: () => of(response) });

    button(fixture, 'Eigenen Zugang einladen')?.click();
    await settle();

    expect(dialog.open.mock.calls[0][1].data).toEqual({
      memberId: 'm-1',
      memberName: 'Lena Ahrens',
      relation: 'self',
    });
    http.expectOne('/api/members/m-1/access').flush([response.access]);
  });

  it('entfernt einen Zugang nach Bestätigung', async () => {
    const fixture = await render(yearsAgo(10), [MOTHER]);
    dialog.open.mockReturnValue({ afterClosed: () => of(true) });

    button(fixture, 'Entfernen')?.click();
    await settle();
    const request = http.expectOne('/api/members/m-1/access/a-1');
    expect(request.request.method).toBe('DELETE');
    request.flush(null);
    await settle();
    http.expectOne('/api/members/m-1/access').flush([]);
  });
});
