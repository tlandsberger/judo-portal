import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { OidcSecurityService } from 'angular-auth-oidc-client';
import { MeResponse, MemberResponse, MyMemberResponse } from '../../api/api-types';
import { fakeOidc } from '../../testing/fake-oidc';
import { HomePage } from './home';

describe('HomePage', () => {
  let http: HttpTestingController;

  async function render() {
    await TestBed.configureTestingModule({
      imports: [HomePage],
      providers: [
        provideRouter([]),
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

  /** Wartet auf das Rendern nach einer Antwort, ohne auf noch offene Requests zu warten. */
  const settle = async () => {
    await new Promise((resolve) => setTimeout(resolve));
    TestBed.tick();
  };

  function member(firstName: string, birthDate: string): MemberResponse {
    return {
      id: firstName,
      firstName,
      lastName: 'Muster',
      birthDate,
      gender: 'female',
      membershipType: 'active',
      entryDate: '2019-08-01',
      left: false,
      version: 0,
    };
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
    await settle();
    http.expectOne('/api/me/members').flush([]);
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
    await settle();
    http.expectOne('/api/me/members').flush([]);
  });

  it('zeigt Eltern ihre Kinder und blendet leere Rollen aus', async () => {
    const fixture = await render();
    http
      .expectOne('/api/me')
      .flush({ subject: '7', displayName: 'Maria Muster', email: null, roles: [] });
    await settle();
    const mine: MyMemberResponse[] = [
      { relation: 'self', member: member('Maria', '1985-01-01') },
      { relation: 'guardian', member: member('Emma', '2017-06-01') },
    ];
    http.expectOne('/api/me/members').flush(mine);
    await fixture.whenStable();

    const text = (fixture.nativeElement as HTMLElement).textContent;
    expect(text).toContain('Meine Mitgliedschaft');
    expect(text).toContain('Mein Kind');
    expect(text).toContain('Emma Muster');
    expect(text).not.toContain('Deine Rollen');
    const link = (fixture.nativeElement as HTMLElement).querySelector('a[aria-label*="Emma"]');
    expect(link?.getAttribute('href')).toBe('/my/members/Emma');
  });
});
