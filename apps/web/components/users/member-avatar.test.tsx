import { describe, expect, it } from "vitest";

import { initialsFor } from "./member-avatar";

describe("initialsFor", () => {
  it("uses first and last name initials when a full name with two parts is present", () => {
    expect(initialsFor("Ada Lovelace", "ada@example.test")).toBe("AL");
  });

  it("falls back to the first two characters of a single-word name", () => {
    expect(initialsFor("Cher", "cher@example.test")).toBe("CH");
  });

  it("falls back to the email when no name is present", () => {
    expect(initialsFor(null, "admin@example.test")).toBe("AD");
  });
});
