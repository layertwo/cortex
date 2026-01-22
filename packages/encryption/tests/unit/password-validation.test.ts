/**
 * Unit tests for password validation functions
 */

import {
  validatePasswordStrength,
  validatePassword,
} from '../../src/lib/password-validation';

describe('Password Validation', () => {
  describe('validatePasswordStrength', () => {
    it('should accept a strong password', () => {
      const result = validatePasswordStrength('MySecureP@ssw0rd2024');

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should reject password shorter than 12 characters', () => {
      const result = validatePasswordStrength('Short1!');

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Password must be at least 12 characters long');
    });

    it('should reject password without uppercase letters', () => {
      const result = validatePasswordStrength('mypassword123!');

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Password must contain at least one uppercase letter');
    });

    it('should reject password without lowercase letters', () => {
      const result = validatePasswordStrength('MYPASSWORD123!');

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Password must contain at least one lowercase letter');
    });

    it('should reject password without numbers', () => {
      const result = validatePasswordStrength('MyPassword!@#');

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Password must contain at least one number');
    });

    it('should reject password without special characters', () => {
      const result = validatePasswordStrength('MyPassword123');

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Password must contain at least one special character');
    });

    it('should reject empty password', () => {
      const result = validatePasswordStrength('');

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Password is required');
    });

    it('should warn about passwords shorter than 16 characters', () => {
      const result = validatePasswordStrength('MyP@ssw0rd12');

      expect(result.isValid).toBe(true);
      expect(result.warnings.length).toBeGreaterThan(0);
      expect(result.warnings.some(w => w.includes('16+ characters'))).toBe(true);
    });

    it('should warn about sequential characters', () => {
      const result = validatePasswordStrength('MyP@ssw0rd123');

      expect(result.isValid).toBe(true);
      expect(result.warnings.some(w => w.includes('sequential characters'))).toBe(true);
    });

    it('should warn about repeated characters', () => {
      const result = validatePasswordStrength('MyP@sssw0rd1');

      expect(result.isValid).toBe(true);
      expect(result.warnings.some(w => w.includes('repeated characters'))).toBe(true);
    });

    it('should accept a very strong password without warnings', () => {
      const result = validatePasswordStrength('xK9#mP2$vL8@qR5!wN7');

      expect(result.isValid).toBe(true);
      expect(result.warnings).toHaveLength(0);
    });
  });

  describe('validatePassword', () => {
    it('should accept a strong, non-breached password', async () => {
      // Using a random strong password that is unlikely to be breached
      const password = 'xK9#mP2$vL8@qR5!wN7yT4';
      
      const result = await validatePassword(password);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    }, 10000); // Increase timeout for API call

    it('should reject a weak password before checking breaches', async () => {
      const result = await validatePassword('weak');

      expect(result.isValid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
      // Should not contain breach error since strength check failed first
      expect(result.errors.some(e => e.includes('data breach'))).toBe(false);
    });

    it('should reject a commonly breached password', async () => {
      // "password123" is a well-known breached password
      const result = await validatePassword('Password123!');

      expect(result.isValid).toBe(false);
      expect(result.errors.some(e => e.includes('data breach'))).toBe(true);
    }, 10000); // Increase timeout for API call
  });
});
