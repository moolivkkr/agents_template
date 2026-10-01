// HARNESS PROBE: with the pack's jest.setup.ts, a request no handler matches must FAIL the call, not reach a
// network or pass with a warning. Proves the option name is the one the installed msw major reads
// (msw 2: onUnhandledRequest, msw 3: onUnhandledFrame — msw 3 ignores the old name and only warns).
import { version } from 'msw/package.json';

test(`msw ${version}: an un-mocked request is rejected`, async () => {
  await expect(fetch('http://localhost:59999/not-mocked')).rejects.toThrow();
});
