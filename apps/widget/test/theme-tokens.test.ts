import { describe, expect, it } from "vitest";
import { chooseReadableForeground, contrastRatio, parseHexColour } from "../src/ui/theme/colour";
import { createWidgetDesignTokens, projectTokensToCssVariables, themeInputFromConfig } from "../src/ui/theme/tokens";
import { validConfig } from "./fixtures";

describe("widget design tokens", () => {
  it("parses hex colours and computes contrast", () => {
    const black = parseHexColour("#000000");
    const white = parseHexColour("#ffffff");
    expect(black).toEqual({ r: 0, g: 0, b: 0 });
    expect(white).toEqual({ r: 255, g: 255, b: 255 });
    expect(contrastRatio(black!, white!)).toBeGreaterThan(20);
  });

  it("rejects invalid colours and falls back deterministically", () => {
    const first = createWidgetDesignTokens({ primaryColour: "javascript:alert(1)", themeMode: "light" });
    const second = createWidgetDesignTokens({ primaryColour: "javascript:alert(1)", themeMode: "light" });
    expect(first.colours["accent-primary"]).toBe("#1f6feb");
    expect(first).toEqual(second);
  });

  it("chooses accessible accent foregrounds", () => {
    const tokens = createWidgetDesignTokens({ primaryColour: "#123456", themeMode: "light" });
    const accent = parseHexColour(tokens.colours["accent-primary"]);
    const foreground = parseHexColour(tokens.colours["accent-contrast"]);
    expect(accent && foreground ? contrastRatio(accent, foreground) : 0).toBeGreaterThanOrEqual(4.5);
    expect(chooseReadableForeground(accent!)).toBe(tokens.colours["accent-contrast"]);
  });

  it("supports light dark and auto mode without changing semantic state colours", () => {
    const light = createWidgetDesignTokens({ primaryColour: "#123456", themeMode: "auto" }, false);
    const dark = createWidgetDesignTokens({ primaryColour: "#123456", themeMode: "auto" }, true);
    expect(light.mode).toBe("light");
    expect(dark.mode).toBe("dark");
    expect(light.colours["state-danger"]).toBe(dark.colours["state-danger"]);
    expect(light.colours["state-warning"]).toBe(dark.colours["state-warning"]);
  });

  it("maps public config to theme inputs without mutating config", () => {
    const before = JSON.stringify(validConfig);
    const input = themeInputFromConfig(validConfig);
    expect(input).toMatchObject({ primaryColour: "#123456", themeMode: "light" });
    createWidgetDesignTokens(input);
    expect(JSON.stringify(validConfig)).toBe(before);
  });

  it("projects CSS custom properties", () => {
    const tokens = createWidgetDesignTokens({ primaryColour: "#123456" });
    const variables = projectTokensToCssVariables(tokens);
    expect(variables["--yw-colours-accent-primary"]).toBe("#123456");
    expect(variables["--yw-focus-width"]).toBe("3px");
  });
});
