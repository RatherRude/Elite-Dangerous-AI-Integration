import { test } from 'node:test';
import assert from 'node:assert/strict';
import { withCorsFallbacks } from '../../electron/cors-headers.js';

test('does not duplicate or override a collector CORS header with different casing', () => {
  const original = {
    'Access-Control-Allow-Origin': ['http://localhost:1420'],
    'ACCESS-CONTROL-ALLOW-HEADERS': ['content-type'],
    'Content-Type': ['application/json'],
  };
  const result = withCorsFallbacks(original);
  assert.equal(Object.keys(result).filter(key => key.toLowerCase() === 'access-control-allow-origin').length, 1);
  assert.deepEqual(result['Access-Control-Allow-Origin'], ['http://localhost:1420']);
  assert.equal(Object.keys(result).filter(key => key.toLowerCase() === 'access-control-allow-headers').length, 1);
  assert.deepEqual(result['Content-Type'], ['application/json']);
  assert.equal(original['access-control-allow-methods'], undefined);
});

test('fills missing CORS headers but preserves existing credential and origin policies', () => {
  const result = withCorsFallbacks({ 'access-control-allow-origin': ['*'], 'Access-Control-Allow-Credentials': ['false'] });
  assert.deepEqual(result['access-control-allow-origin'], ['*']);
  assert.deepEqual(result['Access-Control-Allow-Credentials'], ['false']);
  assert.deepEqual(result['access-control-allow-methods'], ['GET, POST, PUT, DELETE, OPTIONS']);
});
