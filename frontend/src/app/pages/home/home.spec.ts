import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { OidcSecurityService } from 'angular-auth-oidc-client';
import { MeResponse } from '../../api/api-types';
import { fakeOidc } from '../../testing/fake-oidc';
import { HomePage } from './home';

describe('HomePage', () => {
  let http: HttpTestingController;

  async function render() {
    await TestBed.configureTestingModule({
      imports: [HomePage],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: OidcSecurityService, useValue: fakeOidc(true) },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(HomePage);
    // Löst den Request von httpResource aus; whenStable() würde auf die Antwort warten.
    TestBed.tick();
    return fixture;
  }

  afterEach(() => http.verify());

  it('zeigt Name, E-Mail und Rollen auf Deutsch', async () => {
    const fixture = await render();
    const me: MeResponse = {
      subject: '42',
      displayName: 'Tom Trainer',
      email: 'trainer@test.local',
      roles: ['member', 'trainer'],
    };
    http.expectOne('/api/me').flush(me);
    await fixture.whenStable();

    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('Hallo Tom Trainer');
    expect(text).toContain('trainer@test.local');
    expect(text).toContain('Mitglied');
    expect(text).toContain('Übungsleiter');
  });

  it('bietet bei abgelaufener Sitzung eine neue Anmeldung an', async () => {
    const fixture = await render();
    http.expectOne('/api/me').flush(null, { status: 401, statusText: 'Unauthorized' });
    await fixture.whenStable();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Neu anmelden');
  });

  it('bietet bei Serverfehlern "Erneut versuchen" an', async () => {
    const fixture = await render();
    http.expectOne('/api/me').flush(null, { status: 503, statusText: 'Unavailable' });
    await fixture.whenStable();

    const retry = [...(fixture.nativeElement as HTMLElement).querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Erneut versuchen'),
    );
    expect(retry).toBeTruthy();
    retry?.click();
    TestBed.tick();
    http.expectOne('/api/me').flush({ subject: '1', displayName: 'X', email: null, roles: [] });
  });
});
