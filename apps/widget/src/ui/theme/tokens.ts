import type { PublicWidgetConfigResponse } from "../../api/contracts";
import { chooseReadableForeground, deriveInteractiveAccent, deriveMutedAccent, parseHexColour, rgbToHex } from "./colour";

export type WidgetThemeMode = "light" | "dark";
export type WidgetThemePreference = "light" | "dark" | "auto";

export type WidgetDesignTokens = Readonly<{
  mode: WidgetThemeMode;
  colours: Readonly<Record<string, string>>;
  typography: Readonly<Record<string, string>>;
  spacing: Readonly<Record<string, string>>;
  radii: Readonly<Record<string, string>>;
  elevation: Readonly<Record<string, string>>;
  motion: Readonly<Record<string, string>>;
  dimensions: Readonly<Record<string, string>>;
  focus: Readonly<Record<string, string>>;
}>;

export type ThemeInput = Readonly<{
  primaryColour?: string | null;
  secondaryColour?: string | null;
  themeMode?: string | null;
}>;

const FALLBACK_ACCENT = "#1f6feb";
const DARK_FALLBACK_ACCENT = "#7db7ff";

export function themeInputFromConfig(config: PublicWidgetConfigResponse | null): ThemeInput {
  return Object.freeze({
    primaryColour: config?.widget.primary_colour ?? null,
    secondaryColour: config?.widget.secondary_colour ?? null,
    themeMode: config?.widget.theme_mode ?? null,
  });
}

export function resolveThemePreference(value: unknown): WidgetThemePreference {
  return value === "dark" || value === "auto" || value === "light" ? value : "light";
}

export function resolveThemeMode(preference: WidgetThemePreference, systemDark: boolean): WidgetThemeMode {
  if (preference === "auto") return systemDark ? "dark" : "light";
  return preference;
}

export function createWidgetDesignTokens(input: ThemeInput = {}, systemDark = false): WidgetDesignTokens {
  const preference = resolveThemePreference(input.themeMode);
  const mode = resolveThemeMode(preference, systemDark);
  const fallbackAccent = mode === "dark" ? DARK_FALLBACK_ACCENT : FALLBACK_ACCENT;
  const parsedAccent = parseHexColour(input.primaryColour) ?? parseHexColour(fallbackAccent)!;
  const accentHex = rgbToHex(parsedAccent);
  const readableForeground = chooseReadableForeground(parsedAccent, 4.5);
  const safeAccent = readableForeground ? accentHex : fallbackAccent;
  const safeAccentRgb = parseHexColour(safeAccent)!;
  const accentContrast = chooseReadableForeground(safeAccentRgb, 4.5) ?? (mode === "dark" ? "#10131a" : "#ffffff");
  const secondary = parseHexColour(input.secondaryColour) ? input.secondaryColour!.trim() : deriveMutedAccent(safeAccentRgb, mode);

  return deepFreeze({
    mode,
    colours: {
      "surface-canvas": mode === "dark" ? "#10131a" : "#f6f7fb",
      "surface-elevated": mode === "dark" ? "#171c26" : "#ffffff",
      "surface-inset": mode === "dark" ? "#0d1118" : "#eef2f7",
      "surface-overlay": mode === "dark" ? "rgba(6, 9, 14, 0.72)" : "rgba(17, 24, 39, 0.1)",
      "border-subtle": mode === "dark" ? "rgba(255,255,255,0.12)" : "rgba(15,23,42,0.12)",
      "border-strong": mode === "dark" ? "rgba(255,255,255,0.24)" : "rgba(15,23,42,0.24)",
      "text-primary": mode === "dark" ? "#f8fafc" : "#111827",
      "text-secondary": mode === "dark" ? "#cbd5e1" : "#475569",
      "text-muted": mode === "dark" ? "#94a3b8" : "#64748b",
      "text-inverse": accentContrast,
      "accent-primary": safeAccent,
      "accent-secondary": secondary,
      "accent-contrast": accentContrast,
      "accent-muted": deriveMutedAccent(safeAccentRgb, mode),
      "accent-hover": deriveInteractiveAccent(safeAccentRgb, mode),
      "accent-pressed": deriveInteractiveAccent(safeAccentRgb, mode, true),
      "focus-ring": mode === "dark" ? "#fbbf24" : "#0f62fe",
      "state-success": "#15803d",
      "state-warning": "#b45309",
      "state-danger": "#b91c1c",
      "state-fallback": "#6d5bd0",
      "state-low-confidence": "#9a5b13",
      "message-user-surface": safeAccent,
      "message-user-text": accentContrast,
      "message-assistant-surface": mode === "dark" ? "#151b25" : "#ffffff",
      "message-assistant-text": mode === "dark" ? "#f8fafc" : "#111827",
      "citation-surface": mode === "dark" ? "#111827" : "#f8fafc",
    },
    typography: {
      family: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      identity: "650 1rem/1.2 system-ui",
      title: "650 0.95rem/1.25 system-ui",
      body: "400 0.92rem/1.45 system-ui",
      small: "400 0.78rem/1.35 system-ui",
      label: "650 0.82rem/1.2 system-ui",
    },
    spacing: { xs: "0.25rem", sm: "0.5rem", md: "0.75rem", lg: "1rem", xl: "1.25rem", xxl: "1.5rem" },
    radii: { panel: "1.25rem", launcher: "999px", message: "1rem", control: "0.75rem", citation: "0.625rem" },
    elevation: {
      launcher: mode === "dark" ? "0 14px 40px rgba(0,0,0,0.42)" : "0 14px 40px rgba(15,23,42,0.18)",
      panel: mode === "dark" ? "0 28px 80px rgba(0,0,0,0.56)" : "0 28px 80px rgba(15,23,42,0.22)",
    },
    motion: { fast: "120ms", normal: "180ms", slow: "260ms", entrance: "cubic-bezier(0.2, 0.8, 0.2, 1)", exit: "cubic-bezier(0.4, 0, 1, 1)" },
    dimensions: { launcher: "56px", launcherCompact: "52px", panelWidth: "390px", panelHeight: "620px", mobileMargin: "8px" },
    focus: { width: "3px", offset: "3px" },
  });
}

export function projectTokensToCssVariables(tokens: WidgetDesignTokens): Readonly<Record<string, string>> {
  const variables: Record<string, string> = {};
  for (const [group, values] of Object.entries(tokens)) {
    if (group === "mode") continue;
    for (const [key, value] of Object.entries(values as Record<string, string>)) {
      variables[`--yw-${group}-${key}`] = value;
    }
  }
  variables["--yw-color-scheme"] = tokens.mode;
  return Object.freeze(variables);
}

function deepFreeze<T extends object>(value: T): T {
  for (const child of Object.values(value)) {
    if (child && typeof child === "object") deepFreeze(child as Record<string, unknown>);
  }
  return Object.freeze(value);
}
