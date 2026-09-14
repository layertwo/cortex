import { ProgressBar } from '@astryxdesign/core/ProgressBar';

const LABELS = ['Too short', 'Weak', 'Fair', 'Good', 'Strong'] as const;

// Coarse, local, honest: length is the gate, variety adds a step each. The encryption
// package's validatePasswordStrength only gives pass/fail lists, so the meter has its own scale.
export function passwordScore(pw: string): 0 | 1 | 2 | 3 | 4 {
  if (pw.length < 12) return 0;
  let score = 1;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
  if (/\d/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw) || pw.length >= 16) score++;
  return score as 1 | 2 | 3 | 4;
}

export default function PasswordStrength({ password }: { password: string }) {
  const score = passwordScore(password);
  return (
    <ProgressBar
      label="Password strength"
      value={score}
      max={4}
      hasValueLabel
      formatValueLabel={() => LABELS[score]}
      variant={score >= 3 ? 'success' : score === 2 ? 'warning' : 'error'}
    />
  );
}
