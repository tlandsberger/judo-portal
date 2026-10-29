/** Produktion: PWA, API und Keycloak liegen hinter Caddy auf demselben Origin (Schritt 9). */
export const environment = {
  oidc: {
    authority: `${globalThis.location?.origin}/auth/realms/judo`,
    clientId: 'judo-portal-app',
  },
};
