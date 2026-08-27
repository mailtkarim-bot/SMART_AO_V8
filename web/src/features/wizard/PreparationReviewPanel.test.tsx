import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ApiClient } from "../../infrastructure/api";
import { PreparationReviewPanel } from "./PreparationReviewPanel";

function renderPanel() {
  const api = {
    listPreparationReviews: vi.fn().mockResolvedValue({
      package_id: "package-1",
      reviews: [{
        review_id: "review-1",
        package_id: "package-1",
        target_document_id: "document-1",
        target_version: 2,
        revision: 1,
        state: "REQUESTED",
        decision_code: null,
        decision_note: null,
        corrections: [],
      }],
    }),
    decidePreparationReview: vi.fn().mockResolvedValue({ result_code: "PREPARATION_REVIEW_DECIDED" }),
    requestPreparationReview: vi.fn().mockResolvedValue({ result_code: "PREPARATION_REVIEW_REQUESTED" }),
    addPreparationCorrection: vi.fn().mockResolvedValue({ result_code: "PREPARATION_CORRECTION_ADDED" }),
  } as unknown as ApiClient;
  const setMessage = vi.fn();
  render(<PreparationReviewPanel api={api} setMessage={setMessage} />);
  return { api, setMessage };
}

describe("PreparationReviewPanel", () => {
  it("loads latest reviews and sends a server-revisioned acceptance", async () => {
    const { api } = renderPanel();
    fireEvent.change(screen.getByPlaceholderText("UUID du package"), { target: { value: "package-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Charger les revues" }));
    expect(await screen.findByText("document-1 · v2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Accepter" }));
    await waitFor(() => expect(api.decidePreparationReview).toHaveBeenCalledWith("package-1", expect.objectContaining({
      review_id: "review-1",
      target_document_id: "document-1",
      expected_review_revision: 1,
      decision_code: "ACCEPTED",
    })));
  });
});
