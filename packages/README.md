# Cortex Packages

This directory contains the Cortex monorepo packages managed with npm workspaces.

## Packages

### @cortex/encryption

Standalone zero-knowledge encryption library for Cortex. This package provides all cryptographic operations needed for the Cortex productivity suite.

**Features:**
- ChaCha20-Poly1305 authenticated encryption
- Envelope encryption (per-file DEK wrapped with KEK)
- Argon2id key derivation
- HKDF key expansion
- Password validation and breach checking
- Share key derivation
- No framework dependencies - pure TypeScript

**Location:** `packages/encryption/`

**Usage:**
```typescript
import { encrypt, decrypt, deriveVaultMasterKey } from '@cortex/encryption';
```

**Reusability:** This library can be used across:
- Web applications (React, Vue, Angular)
- Mobile applications (React Native)
- Desktop applications (Electron)
- Node.js backends (for testing)

### @cortex/web

React web application for Cortex. This is the main user interface that imports and uses the `@cortex/encryption` library.

**Features:**
- React 18+ with TypeScript
- Vite for build tooling
- Imports `@cortex/encryption` for all crypto operations
- Zero-knowledge architecture

**Location:** `packages/web/`

**Dependencies:**
- `@cortex/encryption` (workspace dependency)
- React, React DOM
- Vite

## Development

### Install Dependencies

From the root directory:
```bash
npm install
```

This will install dependencies for all packages in the workspace.

### Build All Packages

```bash
npm run build
```

### Development Workflow

**Start web app development server:**
```bash
npm run dev:web
```

**Watch encryption library for changes:**
```bash
npm run dev:encryption
```

The web app will automatically pick up changes from the encryption library via workspace linking.

### Testing

**Run all tests:**
```bash
npm test
```

**Run tests for specific package:**
```bash
npm test -w @cortex/encryption
npm test -w @cortex/web
```

## Architecture Benefits

**Separation of Concerns:**
- Encryption logic is isolated from UI code
- Clear boundaries between crypto and application layers
- Easier to audit and test security-critical code

**Reusability:**
- Encryption library can be used in multiple platforms
- Consistent crypto implementation across all clients
- Single source of truth for encryption logic

**Independent Development:**
- Packages can be versioned independently
- Encryption library can be updated without touching UI
- Clear dependency graph

**Better Testing:**
- Crypto library can be thoroughly tested in isolation
- Property-based tests focus on crypto correctness
- UI tests can mock crypto operations
