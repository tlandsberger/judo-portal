import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, UrlTree } from '@angular/router';
import { OidcSecurityService } from 'angular-auth-oidc-client';
import { fakeOidc } from '../testing/fake-oidc';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { firstValueFrom, Observable } from 'rxjs';
import { anonymousGuard, authenticatedGuard, permissionGuard } from './auth.guards';

describe('Guards', () => {
  function run(guard: typeof authenticatedGuard, isAuthenticated: boolean) {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: OidcSecurityService, useValue: fakeOidc(isAuthenticated) },
      ],
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return TestBed.runInInjectionContext(() => guard({} as any, {} as any));
  }

  const url = (result: unknown) => TestBed.inject(Router).serializeUrl(result as UrlTree);

  it('authenticatedGuard lässt Angemeldete durch', () => {
    expect(run(authenticatedGuard, true)).toBe(true);
  });

  it('authenticatedGuard schickt Gäste zur Startseite', () => {
    expect(url(run(authenticatedGuard, false))).toBe('/');
  });

  it('anonymousGuard schickt Angemeldete nach /home', () => {
    expect(url(run(anonymousGuard, true))).toBe('/home');
  });

  it('permissionGuard schickt Gäste zur Startseite', () => {
    expect(url(run(permissionGuard('readMembers'), false))).toBe('/');
  });

  it('permissionGuard wartet auf /api/me und prüft das Recht', async () => {
    const result = run(permissionGuard('readMembers'), true) as Observable<unknown>;
    const decision = firstValueFrom(result);
    TestBed.tick();
    TestBed.inject(HttpTestingController)
      .expectOne('/api/me')
      .flush({ subject: '1', displayName: 'Tom', email: null, roles: ['member', 'trainer'] });
    expect(url(await decision)).toBe('/home');
  });

  it('permissionGuard lässt Abteilungsleiter in die Mitgliederverwaltung', async () => {
    const decision = firstValueFrom(
      run(permissionGuard('writeMembers'), true) as Observable<unknown>,
    );
    TestBed.tick();
    TestBed.inject(HttpTestingController)
      .expectOne('/api/me')
      .flush({ subject: '1', displayName: 'Alex', email: null, roles: ['department_head'] });
    expect(await decision).toBe(true);
  });
});
