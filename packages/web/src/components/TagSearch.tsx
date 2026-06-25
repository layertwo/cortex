import { useState } from 'react';
import { encryptTagForSearch, bytesToBase64 } from '@cortex/encryption';
import { getVaultKeys } from '../vault/keyAccess';
import type { View } from './CollectionSidebar';

export default function TagSearch({
  onSearch,
  onClear,
}: {
  onSearch: (v: View) => void;
  onClear: () => void;
}) {
  const [q, setQ] = useState('');

  async function search() {
    const tag = q.trim();
    if (!tag) return;
    // Same key + vaultId as the upload path so the HMACs match server-side.
    const { vaultId, metadataKey } = await getVaultKeys();
    const encryptedTag = bytesToBase64(encryptTagForSearch(tag, metadataKey, vaultId));
    onSearch({ kind: 'tag', encryptedTag, label: tag });
  }

  return (
    <div>
      <input
        aria-label="search tag"
        value={q}
        placeholder="search by tag"
        onChange={(e) => setQ(e.target.value)}
      />
      <button onClick={search}>Search</button>
      <button
        onClick={() => {
          setQ('');
          onClear();
        }}
      >
        Clear
      </button>
    </div>
  );
}
