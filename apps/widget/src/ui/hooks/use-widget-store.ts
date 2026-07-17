import type { WidgetStateStore, WidgetStateSnapshot } from "../../state/widget-state";
import { useEffect, useState } from "preact/hooks";

export function useWidgetStoreSnapshot(store: WidgetStateStore | null, fallback: WidgetStateSnapshot | null): WidgetStateSnapshot | null {
  const [snapshot, setSnapshot] = useState<WidgetStateSnapshot | null>(() => store?.snapshot() ?? fallback);

  useEffect(() => {
    if (!store) {
      setSnapshot(fallback);
      return undefined;
    }
    return store.subscribe((next) => setSnapshot(next));
  }, [store, fallback]);

  return snapshot;
}
