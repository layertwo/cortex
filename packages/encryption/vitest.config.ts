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
    // Property tests run many Argon2id key derivations. 30s is tight when vitest
    // runs the files in parallel and several derivations contend for CPU.
    testTimeout: 120_000,
    hookTimeout: 30_000,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.ts'],
      exclude: ['src/**/*.d.ts', 'src/index.ts'],
    },
  },
});
