export function isSafeRasterAssetUrl(value: unknown): value is string {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:") return false;
    if (url.username || url.password) return false;
    const pathname = url.pathname.toLowerCase();
    return pathname.endsWith(".png") || pathname.endsWith(".jpg") || pathname.endsWith(".jpeg") || pathname.endsWith(".webp");
  } catch {
    return false;
  }
}

export type SafeAssetProps = Readonly<{
  src: string | null;
  alt: string;
  className?: string;
}>;

export function SafeRasterAsset({ src, alt, className }: SafeAssetProps) {
  if (!isSafeRasterAssetUrl(src)) {
    return <span className={className} aria-hidden="true">Y</span>;
  }
  return <img className={className} src={src} alt={alt} referrerPolicy="no-referrer" decoding="async" />;
}
