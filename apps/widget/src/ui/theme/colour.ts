export type RgbColor = Readonly<{ r: number; g: number; b: number }>;

export function parseHexColour(value: unknown): RgbColor | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  const match = /^#([0-9a-fA-F]{6})$/.exec(trimmed);
  if (!match) return null;
  const hex = match[1];
  return Object.freeze({
    r: Number.parseInt(hex.slice(0, 2), 16),
    g: Number.parseInt(hex.slice(2, 4), 16),
    b: Number.parseInt(hex.slice(4, 6), 16),
  });
}

export function rgbToHex(colour: RgbColor): string {
  return `#${toHex(colour.r)}${toHex(colour.g)}${toHex(colour.b)}`;
}

export function relativeLuminance(colour: RgbColor): number {
  const [r, g, b] = [colour.r, colour.g, colour.b].map((channel) => {
    const value = channel / 255;
    return value <= 0.03928 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a: RgbColor, b: RgbColor): number {
  const l1 = relativeLuminance(a);
  const l2 = relativeLuminance(b);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

export function chooseReadableForeground(background: RgbColor, minimum = 4.5): string | null {
  const white = parseHexColour("#ffffff")!;
  const black = parseHexColour("#10131a")!;
  const whiteRatio = contrastRatio(background, white);
  const blackRatio = contrastRatio(background, black);
  if (whiteRatio >= minimum || blackRatio >= minimum) {
    return whiteRatio >= blackRatio ? rgbToHex(white) : rgbToHex(black);
  }
  return null;
}

export function mixColours(a: RgbColor, b: RgbColor, weight: number): RgbColor {
  const clamped = Math.max(0, Math.min(1, weight));
  return Object.freeze({
    r: Math.round(a.r * (1 - clamped) + b.r * clamped),
    g: Math.round(a.g * (1 - clamped) + b.g * clamped),
    b: Math.round(a.b * (1 - clamped) + b.b * clamped),
  });
}

export function deriveMutedAccent(accent: RgbColor, mode: "light" | "dark"): string {
  const target = parseHexColour(mode === "light" ? "#ffffff" : "#10131a")!;
  return rgbToHex(mixColours(accent, target, mode === "light" ? 0.84 : 0.72));
}

export function deriveInteractiveAccent(accent: RgbColor, mode: "light" | "dark", pressed = false): string {
  const target = parseHexColour(mode === "light" ? "#000000" : "#ffffff")!;
  return rgbToHex(mixColours(accent, target, pressed ? 0.18 : 0.1));
}

function toHex(value: number): string {
  return Math.max(0, Math.min(255, value)).toString(16).padStart(2, "0");
}
