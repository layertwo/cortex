import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import StagedRotationDialog from './StagedRotationDialog';

// rotationLockedAt as the server sends it: epoch seconds.
const STARTED_AT = 1_757_900_000;
const TITLE = 'Finish an earlier password change?';

function setup(props: Partial<React.ComponentProps<typeof StagedRotationDialog>> = {}) {
  const handlers = { onFinish: vi.fn(), onStartOver: vi.fn(), onCancel: vi.fn() };
  render(<StagedRotationDialog startedAt={STARTED_AT} {...handlers} {...props} />);
  return { ...handlers, dialog: screen.getByRole('dialog', { name: TITLE }) };
}

describe('StagedRotationDialog', () => {
  it('explains the earlier change with the date it started', () => {
    const { dialog } = setup();
    expect(dialog).toHaveTextContent(
      `A password change to a different new password was started on ${new Date(STARTED_AT * 1000).toLocaleString()}. Enter that new password to finish it, or start over.`,
    );
  });

  it('says the date is unknown when the server has no lock time', () => {
    const { dialog } = setup({ startedAt: null });
    expect(dialog).toHaveTextContent('was started on an unknown date.');
  });

  it('Finish is disabled until a password is typed, then passes it to onFinish', async () => {
    const { dialog, onFinish } = setup();
    const finish = within(dialog).getByRole('button', { name: 'Finish' });
    expect(finish).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Earlier new password'), 'Earlier1!');
    expect(finish).toBeEnabled();
    await userEvent.click(finish);
    expect(onFinish).toHaveBeenCalledWith('Earlier1!');
  });

  it('Enter in the password field finishes too', async () => {
    const { dialog, onFinish } = setup();
    await userEvent.type(within(dialog).getByLabelText('Earlier new password'), 'Earlier1!{enter}');
    expect(onFinish).toHaveBeenCalledWith('Earlier1!');
  });

  it('Start over and Cancel call their handlers without a password', async () => {
    const { dialog, onStartOver, onCancel, onFinish } = setup();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Start over' }));
    expect(onStartOver).toHaveBeenCalledTimes(1);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onFinish).not.toHaveBeenCalled();
  });

  it('shows the error from a failed finish attempt', () => {
    const { dialog } = setup({ error: 'Incorrect vault password' });
    expect(within(dialog).getByRole('alert')).toHaveTextContent('Incorrect vault password');
  });
});
