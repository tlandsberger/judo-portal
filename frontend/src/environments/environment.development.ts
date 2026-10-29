/** Lokale Entwicklung: Keycloak aus infra/compose.dev.yaml, API über den Dev-Proxy (proxy.conf.json). */
export const environment = {
  oidc: {
    authority: 'http://localhost:8081/realms/judo',
    clientId: 'judo-portal-app',
  },
};
