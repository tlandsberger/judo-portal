import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { OidcSecurityService } from 'angular-auth-oidc-client';
import { App } from './app';
import { fakeOidc } from './testing/fake-oidc';

describe('App', () => {
  async function render(isAuthenticated: boolean) {
    const oidc = fakeOidc(isAuthenticated);
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([]), { provide: OidcSecurityService, useValue: oidc }],
    }).compileComponents();
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    return { element: fixture.nativeElement as HTMLElement, oidc };
  }

  it('zeigt den Vereinsnamen in der Toolbar', async () => {
    const { element } = await render(false);
    expect(element.querySelector('.brand')?.textContent).toContain('WTSV Judo');
  });

  it('zeigt "Abmelden" nur für angemeldete Nutzer', async () => {
    const { element } = await render(false);
    expect(element.textContent).not.toContain('Abmelden');
  });

  it('meldet über Keycloak ab', async () => {
    const { element, oidc } = await render(true);
    const button = [...element.querySelectorAll('button')].find((b) =>
      b.textContent?.includes('Abmelden'),
    );
    button?.click();
    expect(oidc.logoff).toHaveBeenCalled();
  });
});
