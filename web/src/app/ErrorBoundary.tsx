import { Component, Fragment, type ErrorInfo, type ReactNode } from "react";

type ErrorBoundaryProps = {
  children: ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
  resetKey: number;
};

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false, resetKey: 0 };

  static getDerivedStateFromError(): Partial<ErrorBoundaryState> {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("SMART_AO_RENDER_ERROR", { error, componentStack: info.componentStack });
  }

  private reset = (): void => {
    this.setState((state) => ({ hasError: false, resetKey: state.resetKey + 1 }));
  };

  render(): ReactNode {
    if (!this.state.hasError) {
      return <Fragment key={this.state.resetKey}>{this.props.children}</Fragment>;
    }
    return (
      <main role="alert" aria-live="assertive">
        <h1>Le cockpit a rencontré un problème</h1>
        <p>Les données n’ont pas été supprimées. Recharge la section pour reprendre.</p>
        <button type="button" onClick={this.reset}>
          Réessayer
        </button>
      </main>
    );
  }
}
