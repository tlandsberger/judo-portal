import { permissionsFor } from './permissions';

describe('permissionsFor', () => {
  it('Vorstand liest und pflegt Mitglieder, löscht aber nicht', () => {
    expect(permissionsFor(['member', 'board'])).toEqual({
      readMembers: true,
      writeMembers: true,
      deleteMembers: false,
    });
  });

  it('Kasse liest nur', () => {
    expect(permissionsFor(['member', 'treasurer'])).toEqual({
      readMembers: true,
      writeMembers: false,
      deleteMembers: false,
    });
  });

  it('Übungsleiter und Mitglieder sehen keine Mitglieder', () => {
    expect(permissionsFor(['member', 'trainer']).readMembers).toBe(false);
  });

  it('Administration darf alles', () => {
    expect(permissionsFor(['admin'])).toEqual({
      readMembers: true,
      writeMembers: true,
      deleteMembers: true,
    });
  });
});
