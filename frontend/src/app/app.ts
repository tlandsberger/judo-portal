import { Component, computed, inject } from '@angular/core';
import { NgOptimizedImage } from '@angular/common';
import { RouterLink, RouterOutlet } from '@angular/router';
import { MatButton } from '@angular/material/button';
import { MatToolbar } from '@angular/material/toolbar';
import { OidcSecurityService } from 'angular-auth-oidc-client';

@Component({
  selector: 'judo-root',
  imports: [RouterOutlet, RouterLink, NgOptimizedImage, MatToolbar, MatButton],
  template: `
    <mat-toolbar class="toolbar">
      <a class="brand" routerLink="/">
        <img ngSrc="branding/logo-signet-small.png" width="48" height="40" alt="" priority />
        <span>WTSV Judo</span>
      </a>
      <span class="spacer"></span>
      @if (authenticated()) {
        <button matButton="outlined" type="button" (click)="logout()">Abmelden</button>
      }
    </mat-toolbar>
    <main>
      <router-outlet />
    </main>
  `,
  styleUrl: './app.scss',
})
export class App {
  private readonly oidc = inject(OidcSecurityService);

  protected readonly authenticated = computed(() => this.oidc.authenticated().isAuthenticated);

  /** Beendet auch die Keycloak-Session und kehrt zur Startseite zurück. */
  protected logout(): void {
    this.oidc.logoff().subscribe();
  }
}
