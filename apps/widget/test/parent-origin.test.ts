import { describe, expect, it } from "vitest";
import { resolveParentOriginFromBootstrap, normaliseOrigin } from "../src/parent-origin";
import { IframeShellError } from "../src/errors";

describe("parent origin bootstrap", () => {
  it("accepts matching parent_origin and referrer origins", () => {
    const result = resolveParentOriginFromBootstrap(
      "https://widget.yoranix.com/embed/wpk_live_1234567890abcdef?parent_origin=https%3A%2F%2Fexample.com",
      "https://example.com/page/path",
    );
    expect(result.parentOrigin).toBe("https://example.com");
    expect(result.referrerOrigin).toBe("https://example.com");
  });

  it("rejects mismatch, malformed, opaque, and wildcard-like origins", () => {
    expect(() =>
      resolveParentOriginFromBootstrap(
        "https://widget.yoranix.com/embed/key?parent_origin=https%3A%2F%2Fexample.com",
        "https://other.example/page",
      ),
    ).toThrow(IframeShellError);
    expect(() => normaliseOrigin("null", true)).toThrow(IframeShellError);
    expect(() => normaliseOrigin("*", true)).toThrow(IframeShellError);
    expect(() => normaliseOrigin("https://user:pass@example.com", true)).toThrow(IframeShellError);
    expect(() => normaliseOrigin("http://example.com", true)).toThrow(IframeShellError);
  });
});
