import type { AccessRelation, AccessStatus } from '../../api/api-types';

export const RELATION_LABELS: Record<AccessRelation, string> = {
  self: 'Eigener Zugang',
  guardian: 'Erziehungsberechtigt',
};

export const STATUS_LABELS: Record<AccessStatus, string> = {
  invited: 'Eingeladen',
  active: 'Aktiv',
  expired: 'Abgelaufen (volljährig)',
  missing: 'Konto gelöscht',
};

/** Alter in vollen Jahren – wie `AccessRules` im Backend (verbindlich prüft das Backend). */
export function ageOn(birthDate: string, today: Date): number {
  const [year, month, day] = birthDate.split('-').map(Number);
  const hadBirthday =
    today.getMonth() + 1 > month || (today.getMonth() + 1 === month && today.getDate() >= day);
  return today.getFullYear() - year - (hadBirthday ? 0 : 1);
}
