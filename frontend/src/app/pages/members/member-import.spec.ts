import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { ImportResponse } from '../../api/api-types';
import { MemberImportPage } from './member-import';

const PREVIEW: ImportResponse = {
  created: 1,
  updated: 1,
  unchanged: 0,
  failed: 1,
  rows: [
    {
      line: 4,
      memberNumber: '3',
      name: 'Claussen',
      action: 'error',
      changes: [],
      errors: ['Vorname: Bitte den Vornamen angeben.'],
      notes: [],
    },
    {
      line: 2,
      memberNumber: '1',
      name: 'Ahrens, Lena',
      action: 'create',
      changes: [],
      errors: [],
      notes: ['Keine Anrede – Geschlecht bitte im Portal nachtragen.'],
    },
    {
      line: 3,
      memberNumber: '2',
      name: 'Becker, Jonas',
      action: 'update',
      changes: ['Telefon', 'E-Mail'],
      errors: [],
      notes: [],
    },
  ],
};

describe('MemberImportPage', () => {
  let http: HttpTestingController;

  async function render() {
    await TestBed.configureTestingModule({
      imports: [MemberImportPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(MemberImportPage);
    await fixture.whenStable();
    return fixture;
  }

  /** Datei auswählen wie über den Dialog; liefert den Vorschau-Request. */
  async function choose(fixture: Awaited<ReturnType<typeof render>>) {
    const input = (fixture.nativeElement as HTMLElement).querySelector(
      'input[type=file]',
    ) as HTMLInputElement;
    const file = new File(['Mitgliedsnr\n1'], 'liste.csv', { type: 'text/csv' });
    Object.defineProperty(input, 'files', { value: [file] });
    input.dispatchEvent(new Event('change'));
    return http.expectOne('/api/members/import/preview');
  }

  const settle = async (fixture: Awaited<ReturnType<typeof render>>) => {
    await new Promise((resolve) => setTimeout(resolve));
    await fixture.whenStable();
  };

  afterEach(() => http.verify());

  it('lädt die Datei zur Vorschau hoch und zeigt Zähler, Änderungen, Fehler und Hinweise', async () => {
    const fixture = await render();
    const request = await choose(fixture);
    expect(request.request.body).toBeInstanceOf(FormData);
    expect((request.request.body as FormData).get('file')).toBeInstanceOf(File);
    request.flush(PREVIEW);
    await settle(fixture);

    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('1 mit Fehlern');
    expect(text).toContain('Vorname: Bitte den Vornamen angeben.');
    expect(text).toContain('Ändert: Telefon, E-Mail');
    expect(text).toContain('Geschlecht bitte im Portal nachtragen');
    expect(text).toContain('Import ausführen (1 neu, 1 geändert)');
  });

  it('führt den Import aus und kehrt zur Liste zurück', async () => {
    const fixture = await render();
    const navigate = vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(true);
    (await choose(fixture)).flush(PREVIEW);
    await settle(fixture);

    const execute = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find(
      (b) => b.textContent?.includes('Import ausführen'),
    );
    execute?.click();
    http.expectOne('/api/members/import').flush(PREVIEW);
    await settle(fixture);

    expect(navigate).toHaveBeenCalledWith(['/members']);
  });

  it('zeigt Dateifehler des Backends', async () => {
    const fixture = await render();
    (await choose(fixture)).flush(
      { detail: 'Ungültig', errors: [{ field: 'file', message: 'Es fehlen Spalten: Vorname.' }] },
      { status: 400, statusText: 'Bad Request' },
    );
    await settle(fixture);

    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Es fehlen Spalten: Vorname.',
    );
  });
});
