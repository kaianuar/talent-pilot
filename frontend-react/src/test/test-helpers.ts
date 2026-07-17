/**
 * Test helpers for React Testing Library.
 *
 * Kept in a non-.tsx file so the only-export-components lint rule
 * (which protects React Fast Refresh in dev) doesn't complain about
 * the helper functions living next to a component.
 */
import { type ReactElement } from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { QueryClient } from '@tanstack/react-query';

import { AllProviders } from './test-utils';

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: AllProviders, ...options });
}
