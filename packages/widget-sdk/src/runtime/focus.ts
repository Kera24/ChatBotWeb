export class FocusManager {
  private previousElement?: HTMLElement;

  remember(documentRef: Document): void {
    const active = documentRef.activeElement;
    this.previousElement = active instanceof HTMLElement ? active : undefined;
  }

  focusIframe(iframe: HTMLIFrameElement): void {
    try {
      iframe.focus({ preventScroll: true });
    } catch {
      iframe.focus();
    }
  }

  restore(): void {
    const target = this.previousElement;
    this.previousElement = undefined;
    if (!target?.isConnected) {
      return;
    }
    try {
      target.focus({ preventScroll: true });
    } catch {
      target.focus();
    }
  }
}
