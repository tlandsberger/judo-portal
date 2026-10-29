import type { components } from './schema';

/** Typen aus dem API-Vertrag api/openapi.json (generiert, nie von Hand pflegen). */
export type MeResponse = components['schemas']['MeResponse'];
export type Role = MeResponse['roles'][number];
