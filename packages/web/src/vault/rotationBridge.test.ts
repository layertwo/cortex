import { describe, it, expect, beforeEach } from 'vitest';
import { saveBridge, loadBridge, clearBridge, hasBridge } from './rotationBridge';

const kek1 = new Uint8Array(32).fill(1); // oldKek
const kek2 = new Uint8Array(32).fill(2); // newKek
const mk1 = new Uint8Array(32).fill(3); // oldMetadataKey

beforeEach(() => localStorage.clear());

describe('rotationBridge', () => {
  it('round-trips: save then load recovers old keys', async () => {
    await saveBridge('vault-1', kek1, mk1, kek2);
    expect(hasBridge('vault-1')).toBe(true);
    const result = loadBridge('vault-1', kek2);
    expect(result).not.toBeNull();
    expect(Array.from(result!.oldKek)).toEqual(Array.from(kek1));
    expect(Array.from(result!.oldMetadataKey)).toEqual(Array.from(mk1));
  });

  it('returns null when no bridge exists', () => {
    expect(loadBridge('vault-1', kek2)).toBeNull();
  });

  it('returns null on wrong decryption key', async () => {
    await saveBridge('vault-1', kek1, mk1, kek2);
    const wrongKey = new Uint8Array(32).fill(9);
    expect(loadBridge('vault-1', wrongKey)).toBeNull();
  });

  it('clearBridge removes the entry', async () => {
    await saveBridge('vault-1', kek1, mk1, kek2);
    clearBridge('vault-1');
    expect(hasBridge('vault-1')).toBe(false);
  });
});
