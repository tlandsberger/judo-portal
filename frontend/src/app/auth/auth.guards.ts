import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { OidcSecurityService } from 'angular-auth-oidc-client';

/** Nur für angemeldete Nutzer – sonst zurück zur Startseite. */
export const authenticatedGuard: CanActivateFn = () => {
  const authenticated = inject(OidcSecurityService).authenticated().isAuthenticated;
  return authenticated || inject(Router).parseUrl('/');
};

/** Startseite: Wer schon angemeldet ist, landet direkt auf /home. */
export const anonymousGuard: CanActivateFn = () => {
  const authenticated = inject(OidcSecurityService).authenticated().isAuthenticated;
  return !authenticated || inject(Router).parseUrl('/home');
};
