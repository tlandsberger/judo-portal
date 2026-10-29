import { roleLabel } from './role-labels';

describe('roleLabel', () => {
  it('liefert deutsche Bezeichnungen für alle Portal-Rollen', () => {
    expect(roleLabel('member')).toBe('Mitglied');
    expect(roleLabel('trainer')).toBe('Übungsleiter');
    expect(roleLabel('department_head')).toBe('Abteilungsleiter');
    expect(roleLabel('admin')).toBe('Administrator');
  });
});
