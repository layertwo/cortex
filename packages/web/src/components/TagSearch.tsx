import { useState } from 'react';
import { encryptTagForSearch, bytesToBase64 } from '@cortex/encryption';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Icon } from '@astryxdesign/core/Icon';
import { HStack } from '@astryxdesign/core/HStack';
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

  function clear() {
    setQ('');
    onClear();
  }

  return (
    <HStack gap={2} vAlign="end">
      <TextInput
        label="Search tag"
        isLabelHidden
        placeholder="Search by tag"
        size="sm"
        width={200}
        startIcon={<Icon icon="search" />}
        value={q}
        onChange={setQ}
        onEnter={() => void search()}
      />
      <Button label="Search" size="sm" onClick={() => void search()} />
      <Button label="Clear" size="sm" variant="ghost" onClick={clear} />
    </HStack>
  );
}
