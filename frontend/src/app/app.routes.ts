import { Routes } from '@angular/router';
import { anonymousGuard, authenticatedGuard } from './auth/auth.guards';

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
  { path: '**', redirectTo: '' },
];
