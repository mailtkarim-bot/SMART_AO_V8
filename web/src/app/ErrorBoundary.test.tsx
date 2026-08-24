import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ErrorBoundary from "./ErrorBoundary";

function BrokenPanel(): never {
  throw new Error("render failure");
}

describe("ErrorBoundary", () => {
  it("shows a recoverable fallback when a child throws", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    try {
      render(
        <ErrorBoundary>
          <BrokenPanel />
        </ErrorBoundary>,
      );

      expect(screen.getByRole("alert")).toHaveTextContent("problème");
      fireEvent.click(screen.getByRole("button", { name: "Réessayer" }));
      expect(screen.getByRole("alert")).toBeInTheDocument();
    } finally {
      consoleError.mockRestore();
    }
  });
});
