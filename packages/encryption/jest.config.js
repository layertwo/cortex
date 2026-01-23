export default {
  preset: 'ts-jest/presets/default-esm',
  testEnvironment: 'node',
  extensionsToTreatAsEsm: ['.ts'],
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
    '^@noble/ciphers/chacha$': '@noble/ciphers/chacha.js',
    '^@noble/hashes/hmac$': '@noble/hashes/hmac.js',
    '^@noble/hashes/sha2$': '@noble/hashes/sha2.js',
    '^@noble/hashes/hkdf$': '@noble/hashes/hkdf.js',
    '^@noble/hashes/legacy$': '@noble/hashes/legacy.js',
  },
  transform: {
    '^.+\\.tsx?$': [
      'ts-jest',
      {
        useESM: true,
      },
    ],
  },
  testMatch: [
    '**/tests/**/*.test.ts',
    '**/tests/**/*.test.tsx'
  ],
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/**/index.ts'
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html'],
  verbose: true,
  transformIgnorePatterns: [
    'node_modules/(?!(@noble|@scure)/)',
  ],
};
