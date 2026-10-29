import { Provider } from '@angular/core';
import { MAT_FORM_FIELD_DEFAULT_OPTIONS } from '@angular/material/form-field';

/**
 * Einheitliche Formularfelder: umrandet, mit hellem Hintergrund, damit das Vereinsgrün im Label
 * genug Kontrast hat (WCAG AA). Nur in nachgeladenen Routen einbinden (`providers` der
 * Feature-Routen), sonst landet das Form-Field-Modul im Start-Bundle.
 */
export function provideFormDefaults(): Provider[] {
  return [{ provide: MAT_FORM_FIELD_DEFAULT_OPTIONS, useValue: { appearance: 'outline' } }];
}
