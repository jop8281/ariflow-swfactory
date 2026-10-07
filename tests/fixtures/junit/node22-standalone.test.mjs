import { test } from 'node:test';
import assert from 'node:assert/strict';
test('passing test', () => assert.equal(1, 1));
test('historical TODO failure', { todo: 'documented ambiguity' }, () => assert.equal(1, 2));
test('skipped case', { skip: 'not qualified' }, () => {});
