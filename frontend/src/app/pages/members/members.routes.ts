import { Routes } from '@angular/router';
import { permissionGuard } from '../../auth/auth.guards';
import { provideFormDefaults } from '../../shared/form-defaults';

/** Mitgliederverwaltung (`/members`), nachgeladen. Zugriff prüft `permissionGuard` in `app.routes.ts`. */
export const MEMBER_ROUTES: Routes = [
  {
    path: '',
    providers: [provideFormDefaults()],
    children: [
      {
        path: '',
        title: 'Mitglieder – WTSV Judo',
        loadComponent: () => import('./member-list').then((m) => m.MemberListPage),
      },
      {
        path: 'new',
        title: 'Mitglied anlegen – WTSV Judo',
        canActivate: [permissionGuard('writeMembers')],
        loadComponent: () => import('./member-edit').then((m) => m.MemberEditPage),
      },
      {
        path: ':id',
        title: 'Mitglied – WTSV Judo',
        loadComponent: () => import('./member-edit').then((m) => m.MemberEditPage),
      },
    ],
  },
];
