// HARNESS: jest-dom matchers, plus the pointer-capture / scrollIntoView methods jsdom lacks and Radix Select
// calls when it opens (a browser has them; this is environment, not app, code).
import "@testing-library/jest-dom/vitest";

const proto = Element.prototype as unknown as Record<string, unknown>;
proto.hasPointerCapture ??= () => false;
proto.setPointerCapture ??= () => {};
proto.releasePointerCapture ??= () => {};
proto.scrollIntoView ??= () => {};

// Vitest runs without globals here, so Testing Library cannot register its own afterEach cleanup
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
afterEach(() => cleanup());
