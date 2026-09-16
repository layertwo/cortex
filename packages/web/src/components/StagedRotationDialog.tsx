import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Dialog, DialogHeader } from '@astryxdesign/core/Dialog';
import { Layout, LayoutContent, LayoutFooter } from '@astryxdesign/core/Layout';
import { TextInput } from '@astryxdesign/core/TextInput';
import { Button } from '@astryxdesign/core/Button';
import { Banner } from '@astryxdesign/core/Banner';
import { Text } from '@astryxdesign/core/Text';
import { VStack } from '@astryxdesign/core/VStack';
import { HStack } from '@astryxdesign/core/HStack';
import type { OnStagedMismatch, StagedDecision } from '../auth/SessionContext';

export interface StagedRotationDialogProps {
  // The server's rotationLockedAt: epoch seconds (`int(time.time())`), null when unknown.
  startedAt: number | null;
  error?: string;
  onFinish(password: string): void;
  onStartOver(): void;
  onCancel(): void;
}

function startedOn(startedAt: number | null): string {
  return startedAt ? new Date(startedAt * 1000).toLocaleString() : 'an unknown date';
}

// Shown mid-rotation when the server holds a staged salt/verifier pair that the password the
// user just typed does not open: an earlier attempt used a different new password. Rendered
// always-open; the owner mounts it to ask and unmounts it once a callback fires.
export default function StagedRotationDialog({ startedAt, error, onFinish, onStartOver, onCancel }: StagedRotationDialogProps) {
  const [password, setPassword] = useState('');
  const finish = () => {
    if (password) onFinish(password);
  };
  return (
    <Dialog isOpen onOpenChange={(open) => !open && onCancel()} purpose="form" width={480}>
      <Layout
        height="auto"
        header={<DialogHeader title="Finish an earlier password change?" onOpenChange={() => onCancel()} />}
        content={
          <LayoutContent>
            <VStack gap={3}>
              <Text as="p">
                {`A password change to a different new password was started on ${startedOn(startedAt)}. Enter that new password to finish it, or start over.`}
              </Text>
              <TextInput
                label="Earlier new password"
                type="password"
                autoComplete="off"
                hasAutoFocus
                value={password}
                onChange={setPassword}
                onEnter={finish}
              />
              {error && <Banner status="error" title={error} />}
            </VStack>
          </LayoutContent>
        }
        footer={
          <LayoutFooter>
            <HStack gap={2} hAlign="end">
              <Button label="Cancel" variant="ghost" onClick={onCancel} />
              <Button label="Start over" onClick={onStartOver} />
              <Button label="Finish" variant="primary" isDisabled={!password} onClick={finish} />
            </HStack>
          </LayoutFooter>
        }
      />
    </Dialog>
  );
}

type Pending = { startedAt: number | null; error?: string; resolve: (decision: StagedDecision) => void };

// The screen-side half of the `onStagedMismatch` contract: the session's rotation awaits the
// returned promise while the user picks Finish, Start over or Cancel in the dialog. Mount
// `stagedDialog` anywhere in the screen's tree; it is null until the session asks.
export function useStagedMismatch(): { onStagedMismatch: OnStagedMismatch; stagedDialog: ReactNode } {
  const [pending, setPending] = useState<Pending | null>(null);
  const pendingRef = useRef<Pending | null>(null);
  pendingRef.current = pending;
  // If the owning screen unmounts while the dialog is open (e.g. the user navigates away),
  // resolve as a cancel so the awaiting rotateVault does not hang and the server lock is not
  // held forever; the caller's own PAUSE-on-failure path takes it from there.
  useEffect(
    () => () => {
      pendingRef.current?.resolve({ action: 'cancel' });
    },
    [],
  );
  const onStagedMismatch = useCallback<OnStagedMismatch>(
    (startedAt, error) => new Promise((resolve) => setPending({ startedAt, error, resolve })),
    [],
  );
  const settle = (decision: StagedDecision) => {
    pending?.resolve(decision);
    setPending(null);
  };
  const stagedDialog = pending ? (
    <StagedRotationDialog
      startedAt={pending.startedAt}
      error={pending.error}
      onFinish={(password) => settle({ action: 'finish', password })}
      onStartOver={() => settle({ action: 'startOver' })}
      onCancel={() => settle({ action: 'cancel' })}
    />
  ) : null;
  return { onStagedMismatch, stagedDialog };
}
