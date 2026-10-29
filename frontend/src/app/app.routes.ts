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
    path: 'my/members/:id',
    title: 'Meine Daten – WTSV Judo',
    canActivate: [authenticatedGuard],
    loadComponent: () => import('./pages/my/my-member').then((m) => m.MyMemberPage),
  },
  {
    path: 'members',
    canActivate: [authenticatedGuard, permissionGuard('readMembers')],
    loadChildren: () => import('./pages/members/members.routes').then((m) => m.MEMBER_ROUTES),
  },
  { path: '**', redirectTo: '' },
];
