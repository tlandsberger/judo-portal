import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, UrlTree } from '@angular/router';
import { OidcSecurityService } from 'angular-auth-oidc-client';
import { fakeOidc } from '../testing/fake-oidc';
import { anonymousGuard, authenticatedGuard } from './auth.guards';

describe('Guards', () => {
  function run(guard: typeof authenticatedGuard, isAuthenticated: boolean) {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
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
});
