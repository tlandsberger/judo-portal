import { signal } from '@angular/core';
import { of } from 'rxjs';
import { vi } from 'vitest';

/** Minimaler Ersatz für OidcSecurityService in Unit-Tests. */
export function fakeOidc(isAuthenticated: boolean) {
  return {
    authenticated: signal({ isAuthenticated, allConfigsAuthenticated: [] }),
    authorize: vi.fn(),
    logoff: vi.fn(() => of(null)),
  };
}
