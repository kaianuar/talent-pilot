import { vi } from 'vitest';
import '@testing-library/jest-dom/vitest';

// Polyfill scrollIntoView (not available in jsdom)
Element.prototype.scrollIntoView = vi.fn();
