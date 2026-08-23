import { Component, type ErrorInfo, type ReactNode } from "react";

type ErrorBoundaryProps = {
  children: ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
};

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("SMART_AO_RENDER_ERROR", { error, componentStack: info.componentStack });
  }

  private reset = (): void => {
    this.setState({ hasError: false });
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
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
