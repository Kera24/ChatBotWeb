import type { ComponentChildren } from "preact";
import { Component } from "preact";

export type WidgetRenderErrorBoundaryProps = Readonly<{
  children: ComponentChildren;
  onError?: () => void;
}>;

export type WidgetRenderErrorBoundaryState = Readonly<{ failed: boolean }>;

export class WidgetRenderErrorBoundary extends Component<WidgetRenderErrorBoundaryProps, WidgetRenderErrorBoundaryState> {
  override state: WidgetRenderErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): WidgetRenderErrorBoundaryState {
    return { failed: true };
  }

  override componentDidCatch(): void {
    this.props.onError?.();
  }

  override render() {
    if (this.state.failed) {
      return <div className="yw-unavailable" role="alert">The assistant is temporarily unavailable.</div>;
    }
    return this.props.children;
  }
}
