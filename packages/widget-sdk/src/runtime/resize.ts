import type { MountedWidgetFrame } from "./dom";

export type ResizeBounds = Readonly<{
  minWidth: number;
  minHeight: number;
  maxWidth: number;
  maxHeight: number;
}>;

export const DEFAULT_RESIZE_BOUNDS: ResizeBounds = Object.freeze({
  minWidth: 64,
  minHeight: 64,
  maxWidth: 720,
  maxHeight: 800,
});

export function applyResize(frame: MountedWidgetFrame, width: unknown, height: unknown, bounds = DEFAULT_RESIZE_BOUNDS): boolean {
  if (typeof width !== "number" || typeof height !== "number" || !Number.isFinite(width) || !Number.isFinite(height)) {
    return false;
  }
  const nextWidth = clamp(width, bounds.minWidth, Math.min(bounds.maxWidth, window.innerWidth || bounds.maxWidth));
  const nextHeight = clamp(height, bounds.minHeight, Math.min(bounds.maxHeight, window.innerHeight || bounds.maxHeight));
  frame.container.style.width = `${nextWidth}px`;
  frame.container.style.height = `${nextHeight}px`;
  return true;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
