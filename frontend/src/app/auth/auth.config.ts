import { EnvironmentProviders } from '@angular/core';
import { LogLevel, provideAuth, withAppInitializerAuthCheck } from 'angular-auth-oidc-client';
import { environment } from '../../environments/environment';

/**
 * Login per Authorization Code + PKCE gegen Keycloak (ADR 0007).
 * Tokens liegen im sessionStorage (Standard der Bibliothek): nur für dieses Fenster, nie im localStorage.
 */
export function provideOidcAuth(): EnvironmentProviders {
  const origin = globalThis.location.origin;
  return provideAuth(
    {
      config: {
        authority: environment.oidc.authority,
        clientId: environment.oidc.clientId,
        redirectUrl: `${origin}/`,
        postLogoutRedirectUri: `${origin}/`,
        scope: 'openid profile email',
        responseType: 'code',
        silentRenew: true,
        useRefreshToken: true,
        renewTimeBeforeTokenExpiresInSeconds: 30,
        // Keycloak liefert Refresh-Tokens auch ohne offline_access; Offline-Tokens wollen wir bewusst nicht.
        disableRefreshTokenOfflineAccessScopeWarning: true,
        // Das Access-Token nur an die eigene API schicken.
        secureRoutes: ['/api/'],
        logLevel: LogLevel.Warn,
      },
    },
    withAppInitializerAuthCheck(),
  );
}
