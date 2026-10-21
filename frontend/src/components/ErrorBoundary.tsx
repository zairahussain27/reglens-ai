import { Component, type ErrorInfo, type PropsWithChildren } from "react";

export class ErrorBoundary extends Component<PropsWithChildren, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error("UI error", error, info.componentStack); }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="page">
        <h1>Something went wrong</h1>
        <p className="muted">This page hit an unexpected error. Your data is safe.</p>
        <button className="button button-primary" onClick={() => { this.setState({ failed: false }); window.location.hash = "#/home"; }}>Back to Home</button>
      </main>
    );
  }
}
