import { defineTheme } from '@astryxdesign/core/theme';
import { neutralTheme } from '@astryxdesign/theme-neutral';

// Cortex theme: violet accent seeded per scheme, cool violet-tinted greys, high contrast,
// Inter everywhere (loaded by @fontsource-variable/inter in main.tsx), corners at 0.875x.
// Rebuild after any edit: `npm run theme:build` (from packages/web). Built files are committed.
export const cortexTheme = defineTheme({
  name: 'cortex',
  extends: neutralTheme,
  color: { accent: ['#7431E0', '#A78BFA'], neutralStyle: 'cool', contrast: 'high' },
  typography: { body: { family: 'Inter Variable', fallbacks: '-apple-system, system-ui, sans-serif' } },
  radius: { base: 4, multiplier: 0.875 },
  // `typography.heading` weights only apply when `typography.scale` is set, so the h1 weight
  // is pinned directly as a token instead.
  tokens: { '--text-heading-1-weight': 'var(--font-weight-bold)' },
});
