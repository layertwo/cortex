import { defineConfig } from 'vitest/config';

// Jest mapped these extensionless @noble subpaths; Vitest resolves package exports,
// which require the .js suffix in @noble v2.
const noble = (subpath: string) => ({
  find: new RegExp(`^@noble\\/(?:ciphers|hashes)\\/${subpath}$`),
  replacement: `@noble/${subpath.startsWith('chacha') ? 'ciphers' : 'hashes'}/${subpath}.js`,
});

export default defineConfig({
  resolve: {
    alias: [noble('chacha'), noble('hmac'), noble('sha2'), noble('hkdf'), noble('legacy')],
  },
  test: {
    environment: 'node',
    globals: true,
    include: ['tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.ts'],
      exclude: ['src/**/*.d.ts', 'src/index.ts'],
    },
  },
});
