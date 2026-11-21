/** NextURL canonicalizes loopback names to localhost. Use the original Host
 * for browser origin comparison, while restricting this service to loopback. */
export function acceptsLocalOrigin(origin: string | null, host: string | null, protocol: string, port: string) {
  if (!origin) return true; // CLI requests have no browser Origin header.
  if (!host || !["http:", "https:"].includes(protocol)) return false;
  try {
    const destination = new URL(`${protocol}//${host}`);
    return ["127.0.0.1", "localhost", "[::1]"].includes(destination.hostname)
      && destination.host === host
      && destination.port === port
      && origin === destination.origin;
  } catch {
    return false;
  }
}
