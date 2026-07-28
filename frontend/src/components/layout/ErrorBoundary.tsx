import { Button } from "@/components/ui/button";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Catches render-time errors anywhere below it in the tree and shows a
 * single consistent recovery screen, rather than a blank white page.
 * Wrapped around the whole app in main.tsx; feature modules can nest an
 * additional boundary around a specific risky subtree if needed later.
 *
 * Does not catch errors from async code (e.g. a failed fetch) — those are
 * handled by TanStack Query's error states in api/client.ts instead. This
 * boundary is specifically for unexpected render-time failures.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Unhandled render error", error, info.componentStack);
  }

  private handleReset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center">
          <h1 className="font-display text-2xl font-semibold text-foreground">
            Something went wrong
          </h1>
          <p className="max-w-md text-sm text-muted-foreground">
            The page hit an unexpected error. Try reloading — if it keeps
            happening, the details below can help support track it down.
          </p>
          <div className="flex gap-3">
            <Button variant="primary" onClick={this.handleReset}>
              Try again
            </Button>
            <Button variant="outline" onClick={() => window.location.reload()}>
              Reload page
            </Button>
          </div>
          <pre className="mt-4 max-w-lg overflow-auto rounded-md bg-muted p-3 text-left text-xs text-muted-foreground">
            {this.state.error.message}
          </pre>
        </div>
      );
    }

    return this.props.children;
  }
}
