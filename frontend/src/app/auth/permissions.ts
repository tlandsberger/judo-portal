import type { Role } from '../api/api-types';

/**
 * Was der Nutzer in der Oberfläche sehen bzw. anbieten soll. Spiegelt die Rollenprüfung im Backend
 * (z. B. `MemberController`); verbindlich ist allein das Backend, das hier steuert nur die Anzeige.
 */
export interface Permissions {
  readMembers: boolean;
  /** Anlegen, Ändern und CSV-Import. */
  writeMembers: boolean;
  deleteMembers: boolean;
}

export function permissionsFor(roles: readonly Role[]): Permissions {
  const hasAny = (...wanted: Role[]) => wanted.some((role) => roles.includes(role));
  return {
    readMembers: hasAny('department_head', 'admin'),
    writeMembers: hasAny('department_head'),
    deleteMembers: hasAny('admin'),
  };
}
