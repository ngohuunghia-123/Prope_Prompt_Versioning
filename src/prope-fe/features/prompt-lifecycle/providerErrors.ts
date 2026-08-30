import { isApiError } from '@/lib/apiClient';
import { isProvidersUnavailable } from '@/features/prompt-lifecycle/providerApi';

/**
 * The i18n keys to try, most specific first.
 *
 * The envelope's machine `code` maps straight to a catalogue key
 * (`lifecycle.providers.error.<code>`), and i18next walks the array until one
 * resolves — so a code with a translated message renders that message, and a
 * code nobody translated yet degrades to the shared "nothing changed" text.
 * There is deliberately no allow-list: the catalogue, not a `Set` in code, is
 * what decides which refusals deserve their own sentence, and a new server
 * code can gain a message by adding one string.
 */
export function providerErrorKeys(error: unknown): string[] {
  if (isProvidersUnavailable(error)) return ['lifecycle.providers.error.mockMode'];
  if (isApiError(error)) {
    return [`lifecycle.providers.error.${error.code}`, 'lifecycle.providers.error.unknown'];
  }
  return ['lifecycle.providers.error.unknown'];
}

/**
 * Interpolation values the catalogue strings may use, when the envelope carries
 * them. Only structured fields the server put in `details` — never the
 * envelope's log-grade `message` (ADR-0053 keeps that out of the UI).
 */
export function providerErrorValues(error: unknown): Record<string, unknown> {
  if (!isApiError(error) || error.details == null) return {};
  const details = error.details as Record<string, unknown>;
  const values: Record<string, unknown> = {};
  if (typeof details.display_name === 'string' && details.display_name.length > 0) {
    values.name = details.display_name;
  }
  return values;
}
