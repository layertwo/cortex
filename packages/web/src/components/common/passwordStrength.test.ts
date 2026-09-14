import { describe, it, expect } from 'vitest';
import { passwordScore } from './PasswordStrength';

describe('passwordScore', () => {
  it('is 0 under twelve characters whatever they are', () => {
    expect(passwordScore('Ab1!Ab1!Ab1')).toBe(0);
  });
  it('climbs with length, mixed case, digits and symbols', () => {
    expect(passwordScore('abcdefghijkl')).toBe(1);
    expect(passwordScore('abcdefghijkL')).toBe(2);
    expect(passwordScore('abcdefghijL1')).toBe(3);
    expect(passwordScore('abcdefghijL1!')).toBe(4);
    expect(passwordScore('abcdefghijklmnoL1')).toBe(4);
  });
});
