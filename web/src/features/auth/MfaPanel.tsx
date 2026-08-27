import { useState, type Dispatch, type FormEvent, type SetStateAction } from "react";

import type { ApiClient } from "../../infrastructure/api";
import type { TotpEnrollment } from "../../shared/types";

type Message = { tone: "success" | "error" | "warning"; text: string };
type MfaPanelProps = {
  api: ApiClient;
  setMessage: Dispatch<SetStateAction<Message | null>>;
};

export function MfaPanel({ api, setMessage }: MfaPanelProps) {
  const [enrollment, setEnrollment] = useState<TotpEnrollment | null>(null);
  const [enrollmentCode, setEnrollmentCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [busy, setBusy] = useState(false);

  async function beginEnrollment() {
    setBusy(true);
    try {
      setEnrollment(await api.beginTotpEnrollment());
      setMessage({ tone: "warning", text: "Enrôlement TOTP préparé. Conservez les codes de récupération avant confirmation." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de démarrer l’enrôlement MFA." });
    } finally {
      setBusy(false);
    }
  }

  async function confirmEnrollment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!enrollment || !enrollmentCode.trim()) return;
    setBusy(true);
    try {
      await api.confirmTotpEnrollment(enrollment.factor_id, enrollmentCode.trim());
      setEnrollment(null);
      setEnrollmentCode("");
      setMessage({ tone: "success", text: "MFA TOTP activée pour cette identité." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Le code TOTP est invalide." });
    } finally {
      setBusy(false);
    }
  }

  async function disableMfa(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!disableCode.trim()) return;
    setBusy(true);
    try {
      await api.disableTotp(disableCode.trim());
      setDisableCode("");
      setMessage({ tone: "success", text: "MFA TOTP désactivée après vérification." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Impossible de désactiver la MFA." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="section-block mfa-section" id="mfa-section">
      <div className="section-heading">
        <div>
          <span className="section-kicker">SÉCURITÉ DE SESSION</span>
          <h2>Authentification multifacteur</h2>
        </div>
        <span className="count-pill">TOTP</span>
      </div>
      <div className="mfa-grid">
        <div className="detail-panel">
          <div className="panel-heading">
            <div>
              <h3>Activer TOTP</h3>
              <p>Associez une application d’authentification à votre identité.</p>
            </div>
          </div>
          {!enrollment ? (
            <button className="primary-button mfa-button" type="button" disabled={busy} onClick={() => void beginEnrollment()}>
              Démarrer l’enrôlement
            </button>
          ) : (
            <form className="mfa-form" onSubmit={confirmEnrollment}>
              <p className="mfa-secret">URI de provisioning : <code>{enrollment.otpauth_uri}</code></p>
              <div className="recovery-codes" aria-label="Codes de récupération">
                <strong>Codes de récupération — à conserver hors de l’application</strong>
                <code>{enrollment.recovery_codes.join(" · ")}</code>
              </div>
              <label><span>Code affiché par l’application</span><input required inputMode="numeric" autoComplete="one-time-code" value={enrollmentCode} onChange={(event) => setEnrollmentCode(event.target.value)} placeholder="123456" /></label>
              <button className="primary-button" type="submit" disabled={busy}>Confirmer l’activation</button>
            </form>
          )}
        </div>
        <div className="detail-panel">
          <div className="panel-heading">
            <div>
              <h3>Désactiver TOTP</h3>
              <p>Une vérification TOTP est obligatoire ; aucun contournement par l’interface.</p>
            </div>
          </div>
          <form className="mfa-form" onSubmit={disableMfa}>
            <label><span>Code TOTP actuel</span><input required inputMode="numeric" autoComplete="one-time-code" value={disableCode} onChange={(event) => setDisableCode(event.target.value)} placeholder="123456" /></label>
            <button className="secondary-button" type="submit" disabled={busy}>Désactiver MFA</button>
          </form>
        </div>
      </div>
    </section>
  );
}
