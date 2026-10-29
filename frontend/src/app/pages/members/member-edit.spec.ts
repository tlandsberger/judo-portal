import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { OidcSecurityService } from 'angular-auth-oidc-client';
import { MemberResponse } from '../../api/api-types';
import { fakeOidc } from '../../testing/fake-oidc';
import { MemberEditPage } from './member-edit';

const ERIKA: MemberResponse = {
  id: 'm-1',
  firstName: 'Erika',
  lastName: 'Muster',
  birthDate: '2012-03-04',
  gender: 'female',
  city: 'Hamburg',
  membershipType: 'active',
  entryDate: '2019-08-01',
  left: false,
  version: 3,
};

describe('MemberEditPage', () => {
  let http: HttpTestingController;

  async function render(id?: string) {
    await TestBed.configureTestingModule({
      imports: [MemberEditPage],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: OidcSecurityService, useValue: fakeOidc(true) },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(MemberEditPage);
    if (id) {
      fixture.componentRef.setInput('id', id);
    }
    TestBed.tick();
    http.expectOne('/api/me').flush({
      subject: '1',
      displayName: 'Alex',
      email: null,
      roles: ['member', 'department_head'],
    });
    if (id) {
      http.expectOne(`/api/members/${id}`).flush(ERIKA);
      // Abteilungsleiter sehen zusätzlich die Zugänge des Mitglieds (Abschnitt rendern, dann laden).
      await new Promise((resolve) => setTimeout(resolve));
      TestBed.tick();
      http.expectOne(`/api/members/${id}/access`).flush([]);
    }
    await fixture.whenStable();
    return fixture;
  }

  const element = (fixture: { nativeElement: unknown }) => fixture.nativeElement as HTMLElement;
  const input = (fixture: { nativeElement: unknown }, label: string) =>
    [...element(fixture).querySelectorAll('mat-form-field')]
      .find((f) => f.querySelector('mat-label')?.textContent?.trim() === label)
      ?.querySelector('input') as HTMLInputElement;
  const type = (field: HTMLInputElement, value: string) => {
    field.value = value;
    field.dispatchEvent(new Event('input'));
  };
  const submit = (fixture: { nativeElement: unknown }) =>
    element(fixture).querySelector('form')?.dispatchEvent(new Event('submit'));

  /** Wartet, bis die asynchrone Speicheraktion (Promise) und das Rendering fertig sind. */
  const settle = async (fixture: { whenStable: () => Promise<unknown> }) => {
    await new Promise((resolve) => setTimeout(resolve));
    await fixture.whenStable();
  };

  afterEach(() => http.verify());

  it('meldet fehlende Pflichtfelder und schickt nichts ab', async () => {
    const fixture = await render();
    submit(fixture);
    await fixture.whenStable();

    expect(element(fixture).textContent).toContain('Bitte den Vornamen angeben.');
    expect(element(fixture).textContent).toContain('Bitte das Geschlecht angeben.');
    http.expectNone('/api/members');
  });

  it('speichert Änderungen mit Version und leert leere Texte zu null', async () => {
    const fixture = await render('m-1');
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    expect(input(fixture, 'Ort').value).toBe('Hamburg');

    type(input(fixture, 'Ort'), ' ');
    submit(fixture);
    await fixture.whenStable();

    const request = http.expectOne('/api/members/m-1');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toMatchObject({ version: 3, city: null, firstName: 'Erika' });
    request.flush({ ...ERIKA, city: null, version: 4 });
    await settle(fixture);
    expect(navigate).toHaveBeenCalledWith(['/members']);
  });

  it('zeigt Feldfehler des Backends am Feld und Konflikte mit "Neu laden"', async () => {
    const fixture = await render('m-1');
    submit(fixture);
    await fixture.whenStable();
    http
      .expectOne('/api/members/m-1')
      .flush(
        { detail: 'Ungültig', errors: [{ field: 'memberNumber', message: 'Schon vergeben.' }] },
        { status: 409, statusText: 'Conflict' },
      );
    await settle(fixture);
    expect(element(fixture).textContent).toContain('Schon vergeben.');

    // Der Serverfehler gilt, bis das Feld geändert wird.
    type(input(fixture, 'Mitgliedsnummer'), '42');
    submit(fixture);
    await fixture.whenStable();
    http
      .expectOne('/api/members/m-1')
      .flush(
        { detail: 'Das Mitglied wurde zwischenzeitlich geändert. Bitte neu laden.' },
        { status: 409, statusText: 'Conflict' },
      );
    await settle(fixture);
    expect(element(fixture).textContent).toContain('zwischenzeitlich geändert');
    expect(element(fixture).textContent).toContain('Neu laden');
  });
});
