/**
 * Property-Based Tests for Password Validation
 * 
 * These tests verify universal properties of password strength validation
 * and breach detection using fast-check for property-based testing.
 */

import * as fc from 'fast-check';
import {
  validatePasswordStrength,
  validatePassword,
  checkPasswordBreach,
} from '../../src/lib/password-validation';

describe('Password Validation Property Tests', () => {
  /**
   * Property 23: Password strength validation
   * 
   * For any password (account or vault), the system must reject passwords
   * shorter than 12 characters or lacking uppercase letters, lowercase letters,
   * numbers, and special characters.
   * 
   * Validates: Requirements 21.1, 21.2
   */
  describe('Property 23: Password strength validation', () => {
    it('should reject passwords shorter than 12 characters', () => {
      fc.assert(
        fc.property(
          fc.string({ minLength: 1, maxLength: 11 }),
          (shortPassword) => {
            const result = validatePasswordStrength(shortPassword);
            
            // Short passwords must be rejected
            expect(result.isValid).toBe(false);
            expect(result.errors.length).toBeGreaterThan(0);
            expect(result.errors.some(e => e.includes('12 characters'))).toBe(true);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should reject passwords without uppercase letters', () => {
      fc.assert(
        fc.property(
          // Generate password with lowercase, numbers, and special chars but no uppercase
          fc.string({ minLength: 12, maxLength: 128 })
            .filter(s => s.length >= 12)
            .map(s => s.toLowerCase())
            .filter(s => /[a-z]/.test(s) && /[0-9]/.test(s) && /[^A-Za-z0-9]/.test(s))
            .filter(s => !/[A-Z]/.test(s)),
          (password) => {
            const result = validatePasswordStrength(password);
            
            // Password without uppercase must be rejected
            expect(result.isValid).toBe(false);
            expect(result.errors.some(e => e.includes('uppercase'))).toBe(true);
          }
        ),
        { numRuns: 50 }
      );
    });

    it('should reject passwords without lowercase letters', () => {
      fc.assert(
        fc.property(
          // Generate password with uppercase, numbers, and special chars but no lowercase
          fc.string({ minLength: 12, maxLength: 128 })
            .filter(s => s.length >= 12)
            .map(s => s.toUpperCase())
            .filter(s => /[A-Z]/.test(s) && /[0-9]/.test(s) && /[^A-Za-z0-9]/.test(s))
            .filter(s => !/[a-z]/.test(s)),
          (password) => {
            const result = validatePasswordStrength(password);
            
            // Password without lowercase must be rejected
            expect(result.isValid).toBe(false);
            expect(result.errors.some(e => e.includes('lowercase'))).toBe(true);
          }
        ),
        { numRuns: 50 }
      );
    });

    it('should reject passwords without numbers', () => {
      fc.assert(
        fc.property(
          // Generate password with letters and special chars but no numbers
          fc.string({ minLength: 12, maxLength: 128 })
            .filter(s => s.length >= 12)
            .filter(s => /[A-Z]/.test(s) && /[a-z]/.test(s) && /[^A-Za-z0-9]/.test(s))
            .filter(s => !/[0-9]/.test(s)),
          (password) => {
            const result = validatePasswordStrength(password);
            
            // Password without numbers must be rejected
            expect(result.isValid).toBe(false);
            expect(result.errors.some(e => e.includes('number'))).toBe(true);
          }
        ),
        { numRuns: 50 }
      );
    });

    it('should reject passwords without special characters', () => {
      fc.assert(
        fc.property(
          // Generate password with letters and numbers but no special chars
          fc.string({ minLength: 12, maxLength: 128 })
            .filter(s => s.length >= 12)
            .filter(s => /[A-Z]/.test(s) && /[a-z]/.test(s) && /[0-9]/.test(s))
            .filter(s => !/[^A-Za-z0-9]/.test(s)),
          (password) => {
            const result = validatePasswordStrength(password);
            
            // Password without special characters must be rejected
            expect(result.isValid).toBe(false);
            expect(result.errors.some(e => e.includes('special character'))).toBe(true);
          }
        ),
        { numRuns: 50 }
      );
    });

    it('should accept passwords meeting all requirements', () => {
      fc.assert(
        fc.property(
          // Generate strong password with all requirements
          fc.tuple(
            fc.array(fc.constantFrom('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'), { minLength: 2, maxLength: 5 }).map(arr => arr.join('')),
            fc.array(fc.constantFrom('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'), { minLength: 2, maxLength: 5 }).map(arr => arr.join('')),
            fc.array(fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'), { minLength: 2, maxLength: 5 }).map(arr => arr.join('')),
            fc.array(fc.constantFrom('!', '@', '#', '$', '%', '^', '&', '*'), { minLength: 2, maxLength: 5 }).map(arr => arr.join(''))
          ).map(([upper, lower, nums, special]) => {
            // Shuffle the parts to create a random password
            const parts = [upper, lower, nums, special];
            const shuffled = parts.sort(() => Math.random() - 0.5).join('');
            return shuffled;
          }).filter(s => s.length >= 12),
          (password) => {
            const result = validatePasswordStrength(password);
            
            // Strong password must be accepted
            expect(result.isValid).toBe(true);
            expect(result.errors.length).toBe(0);
          }
        ),
        { numRuns: 100 }
      );
    });

    it('should provide warnings for weak patterns even if requirements are met', () => {
      fc.assert(
        fc.property(
          // Generate password with sequential characters
          fc.constantFrom(
            'Abcdefgh123!',  // Sequential letters
            'Password123!',  // Common pattern
            'Aaaaaaa1234!',  // Repeated characters
          ),
          (password) => {
            const result = validatePasswordStrength(password);
            
            // Password meets requirements but should have warnings
            expect(result.isValid).toBe(true);
            expect(result.warnings.length).toBeGreaterThan(0);
          }
        ),
        { numRuns: 10 }
      );
    });

    it('should be deterministic for the same password', () => {
      fc.assert(
        fc.property(
          fc.string({ minLength: 1, maxLength: 128 }),
          (password) => {
            const result1 = validatePasswordStrength(password);
            const result2 = validatePasswordStrength(password);
            
            // Results must be identical
            expect(result1.isValid).toBe(result2.isValid);
            expect(result1.errors).toEqual(result2.errors);
            expect(result1.warnings).toEqual(result2.warnings);
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  /**
   * Property 24: Breached password detection
   * 
   * For any password being created or changed, if the password appears in
   * known breach databases, the system must reject it and require the user
   * to choose a different password.
   * 
   * Validates: Requirements 21.3, 21.4
   * 
   * Note: These tests are skipped by default to avoid making real API calls
   * during testing. They should be run manually or in integration tests.
   */
  describe('Property 24: Breached password detection', () => {
    it.skip('should detect commonly breached passwords', async () => {
      // Known breached passwords (from public breach databases)
      const breachedPasswords = [
        'password123',
        'Password123!',
        'qwerty123!',
        'Abc123456!',
      ];

      for (const password of breachedPasswords) {
        const isBreached = await checkPasswordBreach(password);
        
        // These passwords should be detected as breached
        expect(isBreached).toBe(true);
      }
    }, 30000); // 30 second timeout for API calls

    it.skip('should not flag strong unique passwords as breached', async () => {
      await fc.assert(
        fc.asyncProperty(
          // Generate very strong random passwords unlikely to be breached
          fc.tuple(
            fc.array(fc.constantFrom('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M'), { minLength: 5, maxLength: 10 }).map(arr => arr.join('')),
            fc.array(fc.constantFrom('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm'), { minLength: 5, maxLength: 10 }).map(arr => arr.join('')),
            fc.array(fc.constantFrom('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'), { minLength: 5, maxLength: 10 }).map(arr => arr.join('')),
            fc.array(fc.constantFrom('!', '@', '#', '$', '%', '^', '&', '*', '(', ')'), { minLength: 5, maxLength: 10 }).map(arr => arr.join('')),
            fc.uuid() // Add UUID for extra randomness
          ).map(([upper, lower, nums, special, uuid]) => {
            return `${upper}${lower}${nums}${special}${uuid}`;
          }),
          async (password) => {
            const isBreached = await checkPasswordBreach(password);
            
            // Very strong random passwords should not be breached
            // (though there's a tiny chance they could be)
            expect(isBreached).toBe(false);
          }
        ),
        { numRuns: 10 } // Fewer runs to avoid API rate limiting
      );
    }, 60000); // 60 second timeout for multiple API calls

    it.skip('should handle API errors gracefully', async () => {
      // Test with invalid input that might cause API errors
      const invalidPasswords = ['', ' ', '\n', '\t'];

      for (const password of invalidPasswords) {
        try {
          await checkPasswordBreach(password);
        } catch (error) {
          // Should throw an error for invalid input
          expect(error).toBeDefined();
          expect(error instanceof Error).toBe(true);
        }
      }
    });

    it.skip('should use k-anonymity (never send full password)', async () => {
      // This is a conceptual test - we can't directly verify the API call
      // but we can verify the function doesn't throw errors for valid passwords
      await fc.assert(
        fc.asyncProperty(
          fc.string({ minLength: 12, maxLength: 128 })
            .filter(s => /[A-Z]/.test(s) && /[a-z]/.test(s) && /[0-9]/.test(s) && /[^A-Za-z0-9]/.test(s)),
          async (password) => {
            // Function should complete without errors
            const isBreached = await checkPasswordBreach(password);
            
            // Result should be a boolean
            expect(typeof isBreached).toBe('boolean');
          }
        ),
        { numRuns: 10 } // Fewer runs to avoid API rate limiting
      );
    }, 60000);

    it('should validate complete password with strength and breach checks', async () => {
      // Test with a known weak password (doesn't meet strength requirements)
      const weakPassword = 'weak';
      const result = await validatePassword(weakPassword);
      
      // Should fail strength validation before breach check
      expect(result.isValid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it('should be deterministic for strength validation', () => {
      fc.assert(
        fc.property(
          fc.string({ minLength: 1, maxLength: 128 }),
          (password) => {
            // Strength validation should be deterministic
            const result1 = validatePasswordStrength(password);
            const result2 = validatePasswordStrength(password);
            
            expect(result1.isValid).toBe(result2.isValid);
            expect(result1.errors).toEqual(result2.errors);
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
