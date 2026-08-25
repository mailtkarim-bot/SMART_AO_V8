import { useState } from "react";

import type { CreateCaseInput } from "../../shared/types";

type Props = {
  onCreate: (input: CreateCaseInput) => Promise<void>;
  disabled?: boolean;
};

const scopeOptions: Array<{ value: CreateCaseInput["scope_kind"]; label: string }> = [
  { value: "SINGLE_LOT", label: "Lot unique" },
  { value: "MULTI_LOT", label: "Lots multiples" },
  { value: "TRANCHE", label: "Tranche" },
  { value: "VARIANT", label: "Variante" },
  { value: "CUSTOM", label: "Périmètre personnalisé" },
];

const originOptions: Array<{ value: NonNullable<CreateCaseInput["origin_kind"]>; label: string }> = [
  { value: "MANUAL", label: "Création manuelle" },
  { value: "CLIENT_REQUEST", label: "Demande client" },
  { value: "OPPORTUNITY", label: "Opportunité qualifiée" },
  { value: "IMPORT", label: "Import contrôlé" },
];

const initialForm: CreateCaseInput = {
  title: "",
  object_description: "",
  scope_kind: "SINGLE_LOT",
  lot_numbers: [],
  tranche_reference: "",
  variant_reference: "",
  scope_justification: "",
  origin_kind: "MANUAL",
};

export function CreateCasePanel({ onCreate, disabled = false }: Props) {
  const [form, setForm] = useState<CreateCaseInput>(initialForm);
  const [lotText, setLotText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function update<K extends keyof CreateCaseInput>(key: K, value: CreateCaseInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const lots = lotText
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    setSubmitting(true);
    try {
      await onCreate({
        ...form,
        title: form.title.trim(),
        object_description: form.object_description.trim(),
        lot_numbers: lots,
        tranche_reference: form.tranche_reference?.trim() || undefined,
        variant_reference: form.variant_reference?.trim() || undefined,
        scope_justification: form.scope_justification?.trim() || undefined,
      });
      setForm(initialForm);
      setLotText("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="section-block create-case-section" id="create-case-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">NOUVELLE AFFAIRE</span>
          <h2>Créer une affaire</h2>
        </div>
        <span className="rule-tag">Commande idempotente</span>
      </div>
      <p className="section-note">
        Le périmètre est enregistré côté serveur avant toute lecture DCE, chiffrage ou décision.
        Aucun identifiant d’affaire n’est saisi manuellement.
      </p>
      <form className="create-case-form" onSubmit={submit}>
        <label>
          <span>Titre de l’affaire</span>
          <input
            required
            maxLength={240}
            value={form.title}
            onChange={(event) => update("title", event.target.value)}
            placeholder="Ex. Réhabilitation énergétique du groupe scolaire"
          />
        </label>
        <label className="form-wide">
          <span>Objet et description</span>
          <textarea
            required
            maxLength={10_000}
            rows={4}
            value={form.object_description}
            onChange={(event) => update("object_description", event.target.value)}
            placeholder="Décrivez le périmètre fonctionnel connu et les limites actuelles."
          />
        </label>
        <label>
          <span>Type de périmètre</span>
          <select
            value={form.scope_kind}
            onChange={(event) => update("scope_kind", event.target.value as CreateCaseInput["scope_kind"])}
          >
            {scopeOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Numéros de lots</span>
          <input
            value={lotText}
            onChange={(event) => setLotText(event.target.value)}
            placeholder="01, 02A, 04"
          />
          <small>Séparez les lots par des virgules.</small>
        </label>
        <label>
          <span>Référence tranche</span>
          <input
            maxLength={240}
            value={form.tranche_reference ?? ""}
            onChange={(event) => update("tranche_reference", event.target.value)}
            placeholder="Optionnel"
          />
        </label>
        <label>
          <span>Référence variante</span>
          <input
            maxLength={240}
            value={form.variant_reference ?? ""}
            onChange={(event) => update("variant_reference", event.target.value)}
            placeholder="Optionnel"
          />
        </label>
        <label>
          <span>Origine</span>
          <select
            value={form.origin_kind}
            onChange={(event) => update("origin_kind", event.target.value as CreateCaseInput["origin_kind"])}
          >
            {originOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="form-wide">
          <span>Justification du périmètre</span>
          <textarea
            maxLength={2_000}
            rows={3}
            value={form.scope_justification ?? ""}
            onChange={(event) => update("scope_justification", event.target.value)}
            placeholder="Optionnel : hypothèses, exclusions ou points à confirmer."
          />
        </label>
        <div className="form-actions form-wide">
          <button className="primary-button" type="submit" disabled={disabled || submitting}>
            {submitting ? "Création en cours…" : "Créer l’affaire"}<span>→</span>
          </button>
        </div>
      </form>
    </section>
  );
}
