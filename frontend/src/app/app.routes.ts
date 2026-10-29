import { Routes } from '@angular/router';
import { anonymousGuard, authenticatedGuard, permissionGuard } from './auth/auth.guards';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    canActivate: [anonymousGuard],
    loadComponent: () => import('./pages/start/start').then((m) => m.StartPage),
  },
  {
    path: 'home',
    canActivate: [authenticatedGuard],
    loadComponent: () => import('./pages/home/home').then((m) => m.HomePage),
  },
  {
    path: 'members',
    canActivate: [authenticatedGuard, permissionGuard('readMembers')],
    children: [
      {
        path: '',
        title: 'Mitglieder – WTSV Judo',
        loadComponent: () => import('./pages/members/member-list').then((m) => m.MemberListPage),
      },
      {
        path: 'new',
        title: 'Mitglied anlegen – WTSV Judo',
        canActivate: [permissionGuard('writeMembers')],
        loadComponent: () => import('./pages/members/member-edit').then((m) => m.MemberEditPage),
      },
      {
        path: ':id',
        title: 'Mitglied – WTSV Judo',
        loadComponent: () => import('./pages/members/member-edit').then((m) => m.MemberEditPage),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
