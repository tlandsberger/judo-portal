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
    loadChildren: () => import('./pages/members/members.routes').then((m) => m.MEMBER_ROUTES),
  },
  { path: '**', redirectTo: '' },
];
