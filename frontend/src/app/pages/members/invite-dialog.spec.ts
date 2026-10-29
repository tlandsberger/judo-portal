import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MAT_DIALOG_DATA, MatDialogRef } from '@angular/material/dialog';
import { InviteDialog, InviteDialogData } from './invite-dialog';

describe('InviteDialog', () => {
  let http: HttpTestingController;
  const dialogRef = { close: vi.fn() };

  async function render(relation: InviteDialogData['relation']) {
    await TestBed.configureTestingModule({
      imports: [InviteDialog],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: MatDialogRef, useValue: dialogRef },
        {
          provide: MAT_DIALOG_DATA,
          useValue: { memberId: 'm-1', memberName: 'Lena Ahrens', relation },
        },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(InviteDialog);
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
  const settle = async (fixture: { whenStable: () => Promise<unknown> }) => {
    await new Promise((resolve) => setTimeout(resolve));
    await fixture.whenStable();
  };

  afterEach(() => {
    http.verify();
    dialogRef.close.mockReset();
  });

  it('verlangt bei Eltern E-Mail und Namen', async () => {
    const fixture = await render('guardian');
    element(fixture).querySelector('form')?.dispatchEvent(new Event('submit'));
    await fixture.whenStable();

    expect(element(fixture).textContent).toContain('Bitte die E-Mail-Adresse angeben.');
    expect(element(fixture).textContent).toContain('Bitte den Vornamen angeben.');
    http.expectNone('/api/members/m-1/access');
  });

  it('schickt die Einladung ab und schließt mit der Antwort', async () => {
    const fixture = await render('guardian');
    type(input(fixture, 'E-Mail'), ' mutter@example.org ');
    type(input(fixture, 'Vorname'), 'Maria');
    type(input(fixture, 'Nachname'), 'Muster');
    element(fixture).querySelector('form')?.dispatchEvent(new Event('submit'));
    await fixture.whenStable();

    const request = http.expectOne('/api/members/m-1/access');
    expect(request.request.body).toEqual({
      relation: 'guardian',
      email: 'mutter@example.org',
      firstName: 'Maria',
      lastName: 'Muster',
    });
    const response = { access: { id: 'a-1' }, invitationSent: true };
    request.flush(response);
    await settle(fixture);
    expect(dialogRef.close).toHaveBeenCalledWith(response);
  });

  it('fragt beim eigenen Zugang nur die E-Mail ab und zeigt Konflikte', async () => {
    const fixture = await render('self');
    expect(input(fixture, 'Vorname')).toBeFalsy();
    type(input(fixture, 'E-Mail'), 'lena@example.org');
    element(fixture).querySelector('form')?.dispatchEvent(new Event('submit'));
    await fixture.whenStable();

    http
      .expectOne('/api/members/m-1/access')
      .flush(
        { detail: 'Konflikt', errors: [{ field: 'relation', message: 'Hat schon einen Zugang.' }] },
        { status: 409, statusText: 'Conflict' },
      );
    await settle(fixture);
    expect(element(fixture).textContent).toContain('Hat schon einen Zugang.');
    expect(dialogRef.close).not.toHaveBeenCalled();
  });
});
