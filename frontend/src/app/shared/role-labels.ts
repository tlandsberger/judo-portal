import type { Role } from '../api/api-types';

const ROLE_LABELS: Record<Role, string> = {
  member: 'Mitglied',
  trainer: 'Übungsleiter',
  department_head: 'Abteilungsleiter',
  admin: 'Administrator',
};

/** Deutsche Bezeichnung einer Portal-Rolle. */
export function roleLabel(role: Role): string {
  return ROLE_LABELS[role];
}
