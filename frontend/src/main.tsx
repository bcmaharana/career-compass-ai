import { App } from "@/App";
import { ErrorBoundary } from "@/components/layout/ErrorBoundary";
import "@/styles/globals.css";
import React from "react";
import ReactDOM from "react-dom/client";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
