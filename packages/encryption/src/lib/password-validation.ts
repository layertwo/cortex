/**
 * Password Validation Module
 * 
 * Implements password strength validation and breach detection using the
 * Have I Been Pwned API with k-anonymity model.
 */

import { sha1 } from '@noble/hashes/legacy.js';

/**
 * Password validation result
 */
export interface PasswordValidationResult {
  isValid: boolean;
  errors: string[];
  warnings: string[];
}

/**
 * Password strength requirements
 */
const PASSWORD_REQUIREMENTS = {
  minLength: 12,
  requireUppercase: true,
  requireLowercase: true,
  requireNumbers: true,
  requireSpecialChars: true,
};

/**
 * Have I Been Pwned API endpoint
 */
const HIBP_API_URL = 'https://api.pwnedpasswords.com/range/';

/**
 * Validates password strength requirements.
 * 
 * Checks:
 * - Minimum 12 characters
 * - Contains uppercase letters
 * - Contains lowercase letters
 * - Contains numbers
 * - Contains special characters
 * 
 * @param password - The password to validate
 * @returns PasswordValidationResult - Validation result with errors
 * 
 * @example
 * const result = validatePasswordStrength('MyP@ssw0rd123');
 * if (!result.isValid) {
 *   console.error('Password validation failed:', result.errors);
 * }
 */
export function validatePasswordStrength(password: string): PasswordValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  
  if (!password) {
    errors.push('Password is required');
    return { isValid: false, errors, warnings };
  }
  
  // Check minimum length
  if (password.length < PASSWORD_REQUIREMENTS.minLength) {
    errors.push(`Password must be at least ${PASSWORD_REQUIREMENTS.minLength} characters long`);
  }
  
  // Check for uppercase letters
  if (PASSWORD_REQUIREMENTS.requireUppercase && !/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter');
  }
  
  // Check for lowercase letters
  if (PASSWORD_REQUIREMENTS.requireLowercase && !/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter');
  }
  
  // Check for numbers
  if (PASSWORD_REQUIREMENTS.requireNumbers && !/[0-9]/.test(password)) {
    errors.push('Password must contain at least one number');
  }
  
  // Check for special characters
  if (PASSWORD_REQUIREMENTS.requireSpecialChars && !/[^A-Za-z0-9]/.test(password)) {
    errors.push('Password must contain at least one special character');
  }
  
  // Additional warnings for weak patterns
  if (password.length < 16) {
    warnings.push('Consider using a longer password (16+ characters) for better security');
  }
  
  // Check for common patterns
  if (/^[a-z]+$/i.test(password)) {
    warnings.push('Password contains only letters - consider adding numbers and special characters');
  }
  
  if (/^[0-9]+$/.test(password)) {
    warnings.push('Password contains only numbers - consider adding letters and special characters');
  }
  
  // Check for sequential characters
  if (/(?:abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz|012|123|234|345|456|567|678|789)/i.test(password)) {
    warnings.push('Password contains sequential characters - consider using a more random pattern');
  }
  
  // Check for repeated characters
  if (/(.)\1{2,}/.test(password)) {
    warnings.push('Password contains repeated characters - consider using more variety');
  }
  
  return {
    isValid: errors.length === 0,
    errors,
    warnings,
  };
}

/**
 * Checks if a password has been exposed in known data breaches using the
 * Have I Been Pwned API with k-anonymity model.
 * 
 * This function:
 * 1. Computes SHA-1 hash of the password locally
 * 2. Sends only the first 5 characters of the hash to the API
 * 3. Receives a list of hash suffixes that match the prefix
 * 4. Checks locally if the full hash is in the returned list
 * 
 * This ensures the actual password is never transmitted to the API.
 * 
 * @param password - The password to check
 * @returns Promise<boolean> - True if the password has been breached, false otherwise
 * @throws Error if the API request fails
 * 
 * @example
 * const isBreached = await checkPasswordBreach('password123');
 * if (isBreached) {
 *   console.error('This password has been exposed in a data breach!');
 * }
 */
export async function checkPasswordBreach(password: string): Promise<boolean> {
  if (!password) {
    throw new Error('Password is required');
  }
  
  try {
    // Compute SHA-1 hash of the password (required by HIBP API)
    // Note: SHA-1 is used here for API compatibility, not for security
    const passwordBytes = new TextEncoder().encode(password);
    const hashBytes = sha1(passwordBytes);
    
    // Convert hash to uppercase hex string
    const hashHex = Array.from(hashBytes)
      .map(b => b.toString(16).padStart(2, '0'))
      .join('')
      .toUpperCase();
    
    // Split hash into prefix (first 5 chars) and suffix (remaining chars)
    const hashPrefix = hashHex.substring(0, 5);
    const hashSuffix = hashHex.substring(5);
    
    // Query the Have I Been Pwned API with the hash prefix
    const response = await fetch(`${HIBP_API_URL}${hashPrefix}`, {
      method: 'GET',
      headers: {
        'User-Agent': 'Cortex-Password-Validator',
      },
    });
    
    if (!response.ok) {
      throw new Error(`HIBP API request failed: ${response.status} ${response.statusText}`);
    }
    
    // Parse the response (format: "SUFFIX:COUNT\r\n")
    const responseText = await response.text();
    const lines = responseText.split('\r\n');
    
    // Check if our hash suffix is in the list
    for (const line of lines) {
      const [suffix] = line.split(':');
      if (suffix === hashSuffix) {
        return true; // Password has been breached
      }
    }
    
    return false; // Password not found in breach database
  } catch (error) {
    // If the API is unavailable, we should not block the user
    // but we should log the error
    console.error('Failed to check password breach:', error);
    throw new Error(`Failed to check password breach: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Performs complete password validation including strength and breach checking.
 * 
 * This is the main validation function that should be used for both account
 * and vault passwords. It combines strength validation and breach detection.
 * 
 * @param password - The password to validate
 * @returns Promise<PasswordValidationResult> - Complete validation result
 * 
 * @example
 * const result = await validatePassword('MySecureP@ssw0rd2024');
 * if (!result.isValid) {
 *   console.error('Password validation failed:', result.errors);
 * }
 * if (result.warnings.length > 0) {
 *   console.warn('Password warnings:', result.warnings);
 * }
 */
export async function validatePassword(password: string): Promise<PasswordValidationResult> {
  // First check password strength
  const strengthResult = validatePasswordStrength(password);
  
  if (!strengthResult.isValid) {
    // If strength validation fails, don't bother checking breaches
    return strengthResult;
  }
  
  // Check if password has been breached
  try {
    const isBreached = await checkPasswordBreach(password);
    
    if (isBreached) {
      strengthResult.errors.push(
        'This password has been exposed in a data breach and cannot be used. Please choose a different password.'
      );
      strengthResult.isValid = false;
    }
  } catch (error) {
    // If breach check fails, add a warning but don't block the user
    strengthResult.warnings.push(
      'Unable to verify if password has been breached. Please ensure you are using a unique password.'
    );
  }
  
  return strengthResult;
}
