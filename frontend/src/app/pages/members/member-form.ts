import {
  email,
  maxLength,
  required,
  schema,
  validate,
  type SchemaPath,
} from '@angular/forms/signals';
import type { Gender, MemberRequest, MemberResponse, MembershipType } from '../../api/api-types';

/** Formularstand eines Mitglieds. Leere Texte statt `null`, Datumswerte als `JJJJ-MM-TT`. */
export interface MemberFormModel {
  memberNumber: string;
  firstName: string;
  lastName: string;
  birthDate: string;
  gender: Gender | '';
  street: string;
  postalCode: string;
  city: string;
  phone: string;
  email: string;
  membershipType: MembershipType;
  entryDate: string;
  exitDate: string;
}

export type MemberField = keyof MemberFormModel;

/** Datum als `JJJJ-MM-TT` in lokaler Zeit (wie `<input type="date">`). */
export function isoDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function emptyMember(today: string): MemberFormModel {
  return {
    memberNumber: '',
    firstName: '',
    lastName: '',
    birthDate: '',
    gender: '',
    street: '',
    postalCode: '',
    city: '',
    phone: '',
    email: '',
    membershipType: 'active',
    entryDate: today,
    exitDate: '',
  };
}

export const MEMBER_FIELDS = Object.keys(emptyMember('')) as MemberField[];

export function toFormModel(member: MemberResponse): MemberFormModel {
  return {
    memberNumber: member.memberNumber ?? '',
    firstName: member.firstName,
    lastName: member.lastName,
    birthDate: member.birthDate,
    gender: member.gender,
    street: member.street ?? '',
    postalCode: member.postalCode ?? '',
    city: member.city ?? '',
    phone: member.phone ?? '',
    email: member.email ?? '',
    membershipType: member.membershipType,
    entryDate: member.entryDate,
    exitDate: member.exitDate ?? '',
  };
}

/** Wandelt den (gültigen) Formularstand in die API-Eingabe; leere Texte werden `null`. */
export function toRequest(model: MemberFormModel, version: number | null): MemberRequest {
  const text = (value: string) => value.trim() || null;
  return {
    version,
    memberNumber: text(model.memberNumber),
    firstName: model.firstName.trim(),
    lastName: model.lastName.trim(),
    birthDate: model.birthDate,
    gender: model.gender as Gender,
    street: text(model.street),
    postalCode: text(model.postalCode),
    city: text(model.city),
    phone: text(model.phone),
    email: text(model.email),
    membershipType: model.membershipType,
    entryDate: model.entryDate,
    exitDate: model.exitDate || null,
  };
}

function limit(path: SchemaPath<string>, max: number): void {
  maxLength(path, max, { message: `Höchstens ${max} Zeichen.` });
}

/** Prüfungen im Browser; dieselben Regeln prüft das Backend verbindlich (`MemberRequest`). */
export function memberSchema(today: string) {
  return schema<MemberFormModel>((member) => {
    required(member.firstName, { message: 'Bitte den Vornamen angeben.' });
    required(member.lastName, { message: 'Bitte den Nachnamen angeben.' });
    required(member.birthDate, { message: 'Bitte das Geburtsdatum angeben.' });
    validate(member.birthDate, ({ value }) =>
      value() > today
        ? { kind: 'future', message: 'Das Geburtsdatum darf nicht in der Zukunft liegen.' }
        : undefined,
    );
    required(member.gender, { message: 'Bitte das Geschlecht angeben.' });
    required(member.entryDate, { message: 'Bitte das Eintrittsdatum angeben.' });
    validate(member.exitDate, ({ value, valueOf }) =>
      value() && value() < valueOf(member.entryDate)
        ? { kind: 'beforeEntry', message: 'Der Austritt darf nicht vor dem Eintritt liegen.' }
        : undefined,
    );
    email(member.email, { message: 'Bitte eine gültige E-Mail-Adresse angeben.' });
    limit(member.memberNumber, 20);
    limit(member.firstName, 100);
    limit(member.lastName, 100);
    limit(member.street, 200);
    limit(member.postalCode, 10);
    limit(member.city, 100);
    limit(member.phone, 50);
    limit(member.email, 254);
  });
}
