import type { components } from './schema';

/** Typen aus dem API-Vertrag api/openapi.json (generiert, nie von Hand pflegen). */
export type MeResponse = components['schemas']['MeResponse'];
export type Role = MeResponse['roles'][number];

export type MemberResponse = components['schemas']['MemberResponse'];
export type MemberRequest = components['schemas']['MemberRequest'];
export type Gender = NonNullable<MemberResponse['gender']>;
export type MembershipType = MemberResponse['membershipType'];

export type ImportResponse = components['schemas']['ImportResponse'];
export type ImportRow = components['schemas']['ImportRow'];
export type ImportAction = ImportRow['action'];
