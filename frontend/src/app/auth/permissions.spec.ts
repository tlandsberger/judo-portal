import { permissionsFor } from './permissions';

describe('permissionsFor', () => {
  it('Abteilungsleiter liest und pflegt Mitglieder, löscht aber nicht', () => {
    expect(permissionsFor(['member', 'department_head'])).toEqual({
      readMembers: true,
      writeMembers: true,
      deleteMembers: false,
    });
  });

  it('Administrator liest und löscht, ändert aber nicht', () => {
    expect(permissionsFor(['admin'])).toEqual({
      readMembers: true,
      writeMembers: false,
      deleteMembers: true,
    });
  });

  it('Übungsleiter und Mitglieder sehen keine Mitglieder', () => {
    expect(permissionsFor(['member', 'trainer']).readMembers).toBe(false);
    expect(permissionsFor(['member']).readMembers).toBe(false);
  });
});
