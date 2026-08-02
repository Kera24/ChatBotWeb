import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

class MockIntersectionObserver implements IntersectionObserver {
  readonly root: Element | Document | null = null;
  readonly rootMargin: string = "";
  readonly scrollMargin: string = "";
  readonly thresholds: ReadonlyArray<number> = [];
  disconnect() {}
  observe() {}
  takeRecords(): IntersectionObserverEntry[] { return []; }
  unobserve() {}
}

vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);
});
