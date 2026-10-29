import { HttpErrorResponse } from '@angular/common/http';

/** Fehlerantwort des Backends (RFC 9457, siehe `ApiExceptionHandler`). */
export interface ProblemDetails {
  status?: number;
  detail?: string;
  errors?: { field: string; message: string }[];
}

/** Liest Problem Details aus einem HTTP-Fehler; bei anderen Fehlern ein leeres Objekt. */
export function problemDetails(error: unknown): ProblemDetails {
  if (error instanceof HttpErrorResponse && error.error && typeof error.error === 'object') {
    return error.error as ProblemDetails;
  }
  return {};
}
