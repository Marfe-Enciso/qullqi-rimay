import React, { useState } from 'react';
import {
  AlertTriangle,
  Eye,
  FileCheck2,
  Lock,
  Share2,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { ConsentRecord, FinancialProfileReport } from '../types';

interface Props {
  profile: FinancialProfileReport;
  consents: ConsentRecord[];
  onGrantConsent: (
    recipient: string,
    purpose: string,
    acceptedTerms: boolean
  ) => Promise<void>;
  onRevokeConsent: (consentId: string, reason: string) => Promise<void>;
  onInspectToken: (token: string) => Promise<void>;
  sharedPreviewStatus: string | null;
}

export const FinancialProfileModal: React.FC<Props> = ({
  profile,
  consents,
  onGrantConsent,
  onRevokeConsent,
  onInspectToken,
  sharedPreviewStatus,
}) => {
  const [recipient, setRecipient] = useState(
    'Asesor de Inclusión Financiera BCP (Evaluación Informativa)'
  );
  const [purpose, setPurpose] = useState(
    'Presentar historial operativo de 8 semanas para orientación sobre capital de trabajo (vitrina refrigerada)'
  );
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleGrant = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    if (!acceptedTerms) {
      setErrorMsg(
        'Para compartir el perfil, Rosa debe marcar la casilla de consentimiento libre e informado.'
      );
      return;
    }
    try {
      await onGrantConsent(recipient, purpose, acceptedTerms);
      setAcceptedTerms(false);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Error al otorgar consentimiento');
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
            <FileCheck2 className="w-4 h-4" />
            Funciones 7, 8 y 9 • Perfil Financiero y Consentimiento Revocable
          </span>
          <h3 className="text-lg font-bold text-white mt-0.5">
            Perfil Operativo de {profile.entrepreneur.full_name} ({profile.entrepreneur.city})
          </h3>
          <p className="text-xs text-slate-400">
            {profile.entrepreneur.business_name} • {profile.entrepreneur.market_location}
          </p>
        </div>
        <div className="bg-emerald-950/60 border border-emerald-500/40 rounded-xl px-3.5 py-2 text-xs text-emerald-200 font-semibold">
          {profile.operational_tier}
        </div>
      </div>

      {/* Aviso obligatorio de seguridad y no-aprobación BCP */}
      <div className="bg-amber-950/40 border border-amber-500/40 rounded-xl p-3.5 flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-100 leading-relaxed">
          <p className="font-bold text-amber-300 mb-0.5">
            Guardrail Ético y Regulatorio (bcp_approval_claim = false):
          </p>
          {profile.regulatory_disclaimer}
        </div>
      </div>

      {/* Indicadores clave del Perfil Financiero */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
          <span className="text-slate-400">Ventas 8 Semanas</span>
          <div className="text-base font-bold text-emerald-400 mt-0.5">
            S/ {profile.total_sales_8w_pen.toFixed(2)}
          </div>
        </div>
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
          <span className="text-slate-400">Excedente Neto Total</span>
          <div className="text-base font-bold text-white mt-0.5">
            S/ {profile.total_net_8w_pen.toFixed(2)}
          </div>
        </div>
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
          <span className="text-slate-400">Promedio Semanal Libre</span>
          <div className="text-base font-bold text-sky-400 mt-0.5">
            S/ {profile.average_weekly_net_pen.toFixed(2)}
          </div>
        </div>
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3">
          <span className="text-slate-400">Capacidad Ahorro/Cuota (75%)</span>
          <div className="text-base font-bold text-amber-300 mt-0.5">
            S/ {profile.savings_capacity_weekly_pen.toFixed(2)} / sem
          </div>
        </div>
      </div>

      <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs space-y-1.5">
        <p className="text-slate-200 leading-relaxed">
          <strong className="text-emerald-300">Resumen del Perfil: </strong>
          {profile.plain_spanish_summary}
        </p>
        <p className="text-[11px] text-slate-400 font-mono break-all">
          🔒 Hash SHA-256 de Integridad de Evidencias: {profile.evidence_integrity_hash}
        </p>
      </div>

      {/* Formulario para Compartir con Consentimiento Explícito (Función 8) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2">
        <form
          onSubmit={handleGrant}
          className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3 text-xs"
        >
          <h4 className="font-bold text-white flex items-center gap-1.5 text-sm">
            <Share2 className="w-4 h-4 text-emerald-400" />
            8. Compartir Perfil con Consentimiento Informado
          </h4>

          <div>
            <label className="block text-slate-400 mb-1">Entidad o asesor destinatario</label>
            <input
              type="text"
              required
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white"
            />
          </div>

          <div>
            <label className="block text-slate-400 mb-1">Propósito autorizado</label>
            <input
              type="text"
              required
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white"
            />
          </div>

          <label className="flex items-start gap-2 text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={acceptedTerms}
              onChange={(e) => setAcceptedTerms(e.target.checked)}
              className="mt-0.5 accent-emerald-500"
            />
            <span>
              Yo, <strong>{profile.entrepreneur.full_name}</strong>, autorizo expresamente
              compartir mi historial operativo de 8 semanas y entiendo que puedo revocar el
              acceso cuando lo desee.
            </span>
          </label>

          {errorMsg && (
            <div className="text-rose-400 bg-rose-950/40 border border-rose-500/30 rounded-lg p-2">
              {errorMsg}
            </div>
          )}

          <button
            type="submit"
            className="w-full py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <ShieldCheck className="w-4 h-4" />
            Generar Token de Acceso con Consentimiento
          </button>
        </form>

        {/* Panel de Consentimientos Otorgados y Revocación Inmediata (Función 9) */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3 text-xs">
          <h4 className="font-bold text-white flex items-center gap-1.5 text-sm">
            <Lock className="w-4 h-4 text-amber-400" />
            9. Control de Accesos y Revocación Inmediata ({consents.length})
          </h4>

          {sharedPreviewStatus && (
            <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-700 text-[11px] text-emerald-300">
              {sharedPreviewStatus}
            </div>
          )}

          {consents.length === 0 ? (
            <p className="text-slate-400 py-6 text-center">
              Rosa aún no ha compartido su perfil con ninguna entidad.
            </p>
          ) : (
            <div className="space-y-2.5 max-h-[240px] overflow-y-auto">
              {consents.map((c) => (
                <div
                  key={c.id}
                  className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white">{c.recipient_entity}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        c.status === 'ACTIVO'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                      }`}
                    >
                      {c.status}
                    </span>
                  </div>
                  <p className="text-slate-400 text-[11px]">{c.purpose}</p>
                  <p className="text-[10px] font-mono text-slate-500">
                    Token: {c.share_token} • Hash: {c.evidence_hash.slice(0, 16)}…
                  </p>

                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => onInspectToken(c.share_token)}
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-300 flex items-center gap-1 cursor-pointer"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      Probar enlace compartido
                    </button>

                    {c.status === 'ACTIVO' && (
                      <button
                        type="button"
                        onClick={() =>
                          onRevokeConsent(
                            c.id,
                            'Acceso revocado por la titular Rosa Quispe desde su panel de control'
                          )
                        }
                        className="px-2.5 py-1 rounded bg-rose-900/70 hover:bg-rose-700 text-rose-100 flex items-center gap-1 cursor-pointer"
                      >
                        <ShieldAlert className="w-3.5 h-3.5" />
                        Revocar Acceso Ahora
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

