import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 rounded-xl border border-red-500/30 bg-red-950/20 text-red-200 my-4">
          <div className="flex items-center gap-3 mb-2">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
            <h3 className="font-semibold text-red-300">
              {this.props.fallbackTitle || 'Đã xảy ra sự cố khi tải tiện ích này'}
            </h3>
          </div>
          <p className="text-sm text-red-300/80 mb-4 font-mono break-all">
            {this.state.error?.message || 'Lỗi không xác định.'}
          </p>
          <button
            onClick={this.handleReset}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-900/40 hover:bg-red-800/60 text-xs font-medium text-red-200 border border-red-700/50 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Thử tải lại tiện ích
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
