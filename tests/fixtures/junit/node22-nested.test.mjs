import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
test('standalone pass', () => {});
describe('outer', () => {
  test('suite pass', () => {});
  describe('inner', () => {
    test('inner pass', () => {});
    test('inner skip', { skip: 'unavailable' }, () => {});
    test('inner TODO', { todo: 'pending' }, () => { assert.equal(1, 2); });
  });
});
