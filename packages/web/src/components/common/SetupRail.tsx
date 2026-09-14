import { Stepper, Step } from '@astryxdesign/core/Stepper';

export const SETUP_STEPS = ['Account', 'Verify', 'Vault', 'Recovery'] as const;

// Horizontal progress rail for the first-run and recovery flows. `active` is 0-based.
// minimumStepWidth is lowered so four steps fit inside the 400px auth card without
// collapsing into Astryx's summary row.
export default function SetupRail({
  steps,
  active,
}: {
  steps: readonly string[];
  active: number;
}) {
  return (
    <Stepper
      activeStep={active}
      label="Setup progress"
      density="compact"
      horizontalOptions={{ minimumStepWidth: 64, collapsedVariant: 'withLabel' }}
    >
      {steps.map((s, i) => (
        <Step key={s} step={i} label={s} />
      ))}
    </Stepper>
  );
}
