/** Electron preserves response header casing; HTTP header names are insensitive. */
export function withCorsFallbacks(responseHeaders = {}) {
  const headers = { ...responseHeaders };
  const existing = new Set(Object.keys(headers).map(name => name.toLowerCase()));
  const defaults = {
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'access-control-allow-headers': 'Authorization, User-Agent, content-type',
    'access-control-allow-credentials': 'true',
    'access-control-max-age': '86400',
  };
  for (const [name, value] of Object.entries(defaults)) {
    if (!existing.has(name)) headers[name] = [value];
  }
  return headers;
}
