/**
 * Test wrapper providers.
 *
 * Kept in a .tsx file because it returns JSX. Helper functions
 * live in test-helpers.ts (which is .ts, not .tsx, so the
 * only-export-components rule doesn't apply there).
 */
import { type ReactNode } from 'react';
import { ThemeProvider } from '@mui/material/styles';
import { QueryClientProvider } from '@tanstack/react-query';
import theme from '../theme';

import { createTestQueryClient } from './test-helpers';

export function AllProviders({ children }: { children: ReactNode }) {
  const queryClient = createTestQueryClient();
  return (
    <ThemeProvider theme={theme}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
}
