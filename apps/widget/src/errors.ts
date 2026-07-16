import type { SafeProtocolError } from "@yoranix/widget-sdk";

export type IframeShellErrorCode = SafeProtocolError["code"];

export class IframeShellError extends Error {
  constructor(public readonly safeError: SafeProtocolError) {
    super(safeError.message);
    this.name = "IframeShellError";
  }
}
