import { Component, inject } from '@angular/core';
import { NgOptimizedImage } from '@angular/common';
import { MatButton } from '@angular/material/button';
import { OidcSecurityService } from 'angular-auth-oidc-client';

/** Startseite für nicht angemeldete Besucher. */
@Component({
  selector: 'judo-start',
  imports: [NgOptimizedImage, MatButton],
  template: `
    <section class="start">
      <img
        class="logo"
        ngSrc="branding/logo-wedeler-tsv-judo.webp"
        width="1000"
        height="688"
        alt="Wedeler TSV Judo"
        priority
      />
      <h1>Willkommen im Vereinsportal</h1>
      <p>Melde dich mit deinem Vereinskonto an, um Termine, Trainings und deine Daten zu sehen.</p>
      <button matButton="filled" type="button" (click)="login()">Anmelden</button>
    </section>
  `,
  styles: `
    .start {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      gap: 16px;
    }
    .logo {
      width: min(420px, 90%);
      height: auto;
    }
    h1 {
      font: var(--mat-sys-headline-medium);
      margin: 0;
    }
    p {
      color: var(--mat-sys-on-surface-variant);
      margin: 0 0 8px;
    }
  `,
})
export class StartPage {
  private readonly oidc = inject(OidcSecurityService);

  protected login(): void {
    this.oidc.authorize();
  }
}
