import type { Gender, MembershipType } from '../../api/api-types';

export const GENDER_LABELS: Record<Gender, string> = {
  female: 'weiblich',
  male: 'männlich',
  diverse: 'divers',
};

export const MEMBERSHIP_LABELS: Record<MembershipType, string> = {
  active: 'Aktiv',
  passive: 'Passiv',
};
