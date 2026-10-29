import { computed, inject, Service } from '@angular/core';
import { httpResource } from '@angular/common/http';
import { toObservable } from '@angular/core/rxjs-interop';
import { OidcSecurityService } from 'angular-auth-oidc-client';
import { filter, map, Observable, take } from 'rxjs';
import { MeResponse } from '../api/api-types';
import { Permissions, permissionsFor } from './permissions';

/** Der angemeldete Nutzer aus GET /api/me, einmal geladen und von allen Seiten geteilt. */
@Service()
export class CurrentUser {
  private readonly oidc = inject(OidcSecurityService);

  /** Lädt nur, solange jemand angemeldet ist; nach einem neuen Login wird neu geladen. */
  readonly me = httpResource<MeResponse>(() =>
    this.oidc.authenticated().isAuthenticated ? '/api/me' : undefined,
  );

  readonly permissions = computed(() =>
    permissionsFor(this.me.hasValue() ? this.me.value().roles : []),
  );

  private readonly settled = toObservable(this.me.status).pipe(
    filter((status) => status === 'resolved' || status === 'local' || status === 'error'),
  );

  /** Rechte, sobald /api/me geladen (oder fehlgeschlagen) ist – für Guards. */
  whenLoaded(): Observable<Permissions> {
    return this.settled.pipe(
      take(1),
      map(() => this.permissions()),
    );
  }
}
