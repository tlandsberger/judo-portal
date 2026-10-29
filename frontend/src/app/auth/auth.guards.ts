import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { OidcSecurityService } from 'angular-auth-oidc-client';
import { map } from 'rxjs';
import { CurrentUser } from './current-user';
import { Permissions } from './permissions';

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

/**
 * Seite nur mit dem passenden Recht, sonst zurück nach /home. Dient nur der Bedienung,
 * die Daten schützt das Backend.
 */
export function permissionGuard(permission: keyof Permissions): CanActivateFn {
  return () => {
    const router = inject(Router);
    if (!inject(OidcSecurityService).authenticated().isAuthenticated) {
      return router.parseUrl('/');
    }
    return inject(CurrentUser)
      .whenLoaded()
      .pipe(map((permissions) => permissions[permission] || router.parseUrl('/home')));
  };
}
