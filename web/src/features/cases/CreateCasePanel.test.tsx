import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CreateCaseInput } from "../../shared/types";
import { CreateCasePanel } from "./CreateCasePanel";

describe("CreateCasePanel", () => {
  it("submits the bounded case form and normalizes comma-separated lots", async () => {
    const onCreate = vi.fn<(input: CreateCaseInput) => Promise<void>>().mockResolvedValue();
    render(<CreateCasePanel onCreate={onCreate} />);

    fireEvent.change(screen.getByLabelText("Titre de l’affaire"), {
      target: { value: "  Réhabilitation énergétique  " },
    });
    fireEvent.change(screen.getByLabelText("Objet et description"), {
      target: { value: " Travaux sur le groupe scolaire. " },
    });
    fireEvent.change(screen.getByPlaceholderText("01, 02A, 04"), {
      target: { value: "01, 02A, , 04" },
    });
    fireEvent.change(screen.getByPlaceholderText("Optionnel : hypothèses, exclusions ou points à confirmer."), {
      target: { value: "Hypothèse initiale" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Créer l’affaire/ }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledOnce());
    expect(onCreate).toHaveBeenCalledWith({
      title: "Réhabilitation énergétique",
      object_description: "Travaux sur le groupe scolaire.",
      scope_kind: "SINGLE_LOT",
      lot_numbers: ["01", "02A", "04"],
      tranche_reference: undefined,
      variant_reference: undefined,
      scope_justification: "Hypothèse initiale",
      origin_kind: "MANUAL",
    });
    expect(screen.getByLabelText("Titre de l’affaire")).toHaveValue("");
  });

  it("does not call the command boundary when required fields are empty", () => {
    const onCreate = vi.fn<(input: CreateCaseInput) => Promise<void>>();
    render(<CreateCasePanel onCreate={onCreate} />);

    fireEvent.click(screen.getByRole("button", { name: /Créer l’affaire/ }));

    expect(onCreate).not.toHaveBeenCalled();
  });
});
