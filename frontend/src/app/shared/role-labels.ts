import type { Role } from '../api/api-types';

const ROLE_LABELS: Record<Role, string> = {
  member: 'Mitglied',
  trainer: 'Übungsleiter',
  board: 'Vorstand',
  treasurer: 'Kasse',
  admin: 'Administration',
};

/** Deutsche Bezeichnung einer Portal-Rolle. */
export function roleLabel(role: Role): string {
  return ROLE_LABELS[role];
}
