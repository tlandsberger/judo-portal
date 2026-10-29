import { roleLabel } from './role-labels';

describe('roleLabel', () => {
  it('liefert deutsche Bezeichnungen für alle Portal-Rollen', () => {
    expect(roleLabel('member')).toBe('Mitglied');
    expect(roleLabel('trainer')).toBe('Übungsleiter');
    expect(roleLabel('board')).toBe('Vorstand');
    expect(roleLabel('treasurer')).toBe('Kasse');
    expect(roleLabel('admin')).toBe('Administration');
  });
});
