import React, { useEffect, useState } from 'react';
import {
  CheckCircle2,
  Globe,
  KeyRound,
  Link2,
  Lock,
  LogIn,
  Mail,
  Smartphone,
  UserPlus,
  X,
} from 'lucide-react';
import { api } from '../api';
import {
  EntrepreneurProfileInfo,
  LanguageCode,
  WhatsappLinkGenerateResponse,
} from '../types';

interface Props {
  isOpen: boolean;
  initialMode: 'REGISTER' | 'LOGIN' | 'VERIFY_EMAIL' | 'WHATSAPP_LINK';
  initialClaimCode?: string | null;
  currentEntrepreneur?: EntrepreneurProfileInfo | null;
  onClose: () => void;
  onAuthenticated: (entrepreneur: EntrepreneurProfileInfo) => Promise<void>;
}

export const AuthAndWhatsappModal: React.FC<Props> = ({
  isOpen,
  initialMode,
  initialClaimCode,
  currentEntrepreneur,
  onClose,
  onAuthenticated,
}) => {
  const [mode, setMode] = useState<'REGISTER' | 'LOGIN' | 'VERIFY_EMAIL' | 'WHATSAPP_LINK'>(
    initialMode
  );
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);

  // Campos de Registro / Login
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [businessName, setBusinessName] = useState('');
  const [tradeSector, setTradeSector] = useState('Comercio minorista y abarrotes');
  const [marketLocation, setMarketLocation] = useState('Mercado Central');
  const [city, setCity] = useState('Huamanga');
  const [goalTitle, setGoalTitle] = useState(
    'Reunir S/ 1,600 de ganancia neta en 8 semanas para capital de trabajo'
  );
  const [goalTargetPen, setGoalTargetPen] = useState('1600');
  const [preferredLanguage, setPreferredLanguage] = useState<LanguageCode>('es');
  const [acceptedConsent, setAcceptedConsent] = useState(false);
  const [waClaimCode, setWaClaimCode] = useState(initialClaimCode || '');

  // Campos de Verificación de Correo
  const [verificationCode, setVerificationCode] = useState('');
  const [deliveryMode, setDeliveryMode] = useState<string>('');

  // Campos de Vinculación WhatsApp
  const [linkCodeData, setLinkCodeData] = useState<WhatsappLinkGenerateResponse | null>(null);
  const [claimCodeInput, setClaimCodeInput] = useState('');

  useEffect(() => {
    setMode(initialMode);
    setErrorMsg(null);
    setInfoMsg(null);
  }, [initialMode, isOpen]);

  useEffect(() => {
    if (initialClaimCode) {
      setWaClaimCode(initialClaimCode);
      void handleInspectProvisionalCode(initialClaimCode);
    }
  }, [initialClaimCode]);

  if (!isOpen) return null;

  const handleInspectProvisionalCode = async (codeToInspect: string) => {
    const clean = codeToInspect.trim().toUpperCase();
    if (!clean) return;
    try {
      setErrorMsg(null);
      const draft = await api.inspectWhatsappProvisional(clean);
      setFullName(draft.full_name);
      setBusinessName(draft.business_name);
      setCity(draft.city);
      setPreferredLanguage(draft.preferred_language);
      setAcceptedConsent(Boolean(draft.consent_accepted));
      setInfoMsg(
        `📱 Datos pre-cargados desde tu WhatsApp (${draft.phone_masked}): ${draft.full_name} — ${draft.business_name}. Completa tu correo y contraseña para activar tu cuenta.`
      );
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : 'No se encontró el código provisional de WhatsApp.'
      );
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    setInfoMsg(null);
    try {
      const targetNum = parseFloat(goalTargetPen) || 1600;
      const res = await api.registerAccount({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        business_name: businessName.trim(),
        trade_sector: tradeSector.trim(),
        market_location: marketLocation.trim(),
        city: city.trim(),
        region: 'Ayacucho',
        goal_title: goalTitle.trim(),
        goal_target_pen: targetNum,
        preferred_language: preferredLanguage,
        accepted_data_consent: acceptedConsent,
        whatsapp_claim_code: waClaimCode.trim() ? waClaimCode.trim().toUpperCase() : null,
      });
      setDeliveryMode(res.verification_delivery_mode);
      setInfoMsg(res.message);
      setMode('VERIFY_EMAIL');
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Error al registrar cuenta');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    try {
      const session = await api.verifyEmailAndActivate(
        email.trim(),
        verificationCode.trim()
      );
      api.setSupabaseAuthToken(session.access_token);
      await onAuthenticated(session.entrepreneur);
      onClose();
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error ? err.message : 'Código de verificación inválido'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    try {
      const session = await api.loginAccount(email.trim(), password);
      api.setSupabaseAuthToken(session.access_token);
      await onAuthenticated(session.entrepreneur);
      onClose();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Credenciales inválidas');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateWhatsappCode = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await api.generateWhatsappLinkCode();
      setLinkCodeData(res);
    } catch (err: unknown) {
      setErrorMsg(
        err instanceof Error
          ? err.message
          : 'No se pudo generar el código de vinculación'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleClaimProvisionalInLoggedAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!claimCodeInput.trim()) return;
    setLoading(true);
    setErrorMsg(null);
    try {
      const updated = await api.claimWhatsappProvisional(
        claimCodeInput.trim().toUpperCase()
      );
      setInfoMsg(
        `✅ ¡WhatsApp (${updated.phone_masked}) vinculado exitosamente a tu negocio '${updated.business_name}'!`
      );
      await onAuthenticated(updated);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Código inválido');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full p-5 shadow-2xl space-y-4 my-8">
        {/* Cabecera del modal */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-emerald-600 flex items-center justify-center text-white font-bold">
              Q
            </div>
            <div>
              <h2 className="text-base font-bold text-white">
                {mode === 'REGISTER' && 'Crear Cuenta Real de Emprendedora (Supabase Auth)'}
                {mode === 'VERIFY_EMAIL' && 'Verificación de Correo Electrónico'}
                {mode === 'LOGIN' && 'Iniciar Sesión en Qullqi Rimay'}
                {mode === 'WHATSAPP_LINK' && 'Conectar y Empezar en WhatsApp (Twilio Sandbox)'}
              </h2>
              <p className="text-xs text-slate-400">
                Cada cuenta tiene su propio identificador único (owner_user_id + entrepreneur_id) y aislamiento estricto.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar modal"
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Pestañas de modo */}
        {mode !== 'WHATSAPP_LINK' && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMode('REGISTER')}
              className={`flex-1 py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer ${
                mode === 'REGISTER' || mode === 'VERIFY_EMAIL'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              <UserPlus className="w-3.5 h-3.5" />
              Crear Cuenta Nueva
            </button>
            <button
              type="button"
              onClick={() => setMode('LOGIN')}
              className={`flex-1 py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer ${
                mode === 'LOGIN'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              <LogIn className="w-3.5 h-3.5" />
              Ya tengo cuenta (Iniciar Sesión)
            </button>
          </div>
        )}

        {errorMsg && (
          <div className="bg-rose-950/70 border border-rose-500/40 rounded-xl p-3 text-xs text-rose-200">
            ⚠️ {errorMsg}
          </div>
        )}

        {infoMsg && (
          <div className="bg-emerald-950/70 border border-emerald-500/40 rounded-xl p-3 text-xs text-emerald-200">
            {infoMsg}
          </div>
        )}

        {/* MODO 1: REGISTRO WEB REAL */}
        {mode === 'REGISTER' && (
          <form onSubmit={handleRegisterSubmit} className="space-y-3 text-xs">
            {/* Opción de vincular código provisional iniciado desde WhatsApp */}
            <div className="bg-slate-950 border border-emerald-500/30 rounded-xl p-3 space-y-2">
              <label className="block text-emerald-300 font-semibold flex items-center gap-1.5">
                <Smartphone className="w-3.5 h-3.5" />
                ¿Iniciaste tu registro por WhatsApp? (Opcional — Código WA-LINK-XXXXXXXX)
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={waClaimCode}
                  onChange={(e) => setWaClaimCode(e.target.value.toUpperCase())}
                  placeholder="Ej. WA-LINK-A1B2C3D4"
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white font-mono"
                />
                <button
                  type="button"
                  onClick={() => handleInspectProvisionalCode(waClaimCode)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-emerald-300 border border-slate-700 font-medium cursor-pointer"
                >
                  Pre-cargar datos
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-300 mb-1">
                  Correo electrónico *
                </label>
                <div className="relative">
                  <Mail className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="maria.quispe@ejemplo.pe"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">
                  Contraseña segura (mín. 8 caracteres) *
                </label>
                <div className="relative">
                  <Lock className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-3 py-2 text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">
                  Nombre de la emprendedora *
                </label>
                <input
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Ej. María Condori"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">
                  Nombre del negocio o puesto *
                </label>
                <input
                  type="text"
                  required
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  placeholder="Ej. Bodega y Verdulería Sumaq"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Giro comercial</label>
                <input
                  type="text"
                  required
                  value={tradeSector}
                  onChange={(e) => setTradeSector(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Ciudad / Mercado</label>
                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    required
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="Ciudad"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-white"
                  />
                  <input
                    type="text"
                    required
                    value={marketLocation}
                    onChange={(e) => setMarketLocation(e.target.value)}
                    placeholder="Mercado / Puesto"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-2 text-white"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">
                  Meta de ganancia neta a 8 semanas (S/) *
                </label>
                <input
                  type="number"
                  min="100"
                  step="50"
                  required
                  value={goalTargetPen}
                  onChange={(e) => setGoalTargetPen(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1 flex items-center gap-1">
                  <Globe className="w-3.5 h-3.5 text-amber-400" />
                  Idioma preferido (Español o Quechua Ayacuchano) *
                </label>
                <select
                  value={preferredLanguage}
                  onChange={(e) => setPreferredLanguage(e.target.value as LanguageCode)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                >
                  <option value="es">Español</option>
                  <option value="qu">Quechua Ayacuchano (Chanka — sujeto a revisión lingüística)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-slate-300 mb-1">
                Propósito de tu meta de 8 semanas
              </label>
              <input
                type="text"
                required
                value={goalTitle}
                onChange={(e) => setGoalTitle(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
              />
            </div>

            <label className="flex items-start gap-2.5 bg-slate-950 border border-slate-800 rounded-xl p-3 cursor-pointer">
              <input
                type="checkbox"
                required
                checked={acceptedConsent}
                onChange={(e) => setAcceptedConsent(e.target.checked)}
                className="mt-0.5 accent-emerald-500"
              />
              <span className="text-slate-300 leading-relaxed">
                <strong>Consentimiento Informado de Tratamiento de Datos:</strong> Autorizo a Qullqi Rimay a registrar mis ventas y gastos confirmados para calcular mis resúmenes semanales y generar mi Perfil Financiero verificable (revocable en cualquier momento).
              </span>
            </label>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-sm cursor-pointer"
            >
              {loading ? 'Creando cuenta...' : 'Crear Cuenta y Continuar a Verificación de Correo'}
            </button>
          </form>
        )}

        {/* MODO 2: VERIFICACIÓN DE CORREO ELECTRÓNICO OFICIAL SUPABASE AUTH */}
        {mode === 'VERIFY_EMAIL' && (
          <form onSubmit={handleVerifyEmailSubmit} className="space-y-4 text-xs">
            <div className="bg-slate-950 border border-emerald-500/40 rounded-xl p-4 space-y-2.5">
              <div className="flex items-center gap-2 text-emerald-300 font-semibold text-sm">
                <KeyRound className="w-4 h-4" />
                Verificación oficial en Supabase Auth ({email}) • {deliveryMode}
              </div>
              <p className="text-slate-300 leading-relaxed">
                Supabase Auth ha enviado un correo de verificación a <strong>{email}</strong>. Por seguridad, no se emiten códigos locales sin entrega real a tu buzón.
              </p>
              <div className="bg-slate-900 border border-slate-800 rounded-lg p-3 space-y-2 text-slate-300">
                <p>
                  <strong>Opción A (Enlace en tu correo):</strong> Abre el correo de Supabase Auth, haz clic en <em>&ldquo;Confirm your mail&rdquo;</em> y luego pulsa el botón de abajo para iniciar sesión:
                </p>
                <button
                  type="button"
                  onClick={() => setMode('LOGIN')}
                  className="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold cursor-pointer"
                >
                  Ya confirmé el enlace en mi correo → Ir a Iniciar Sesión
                </button>
              </div>
            </div>

            <div>
              <label className="block text-slate-300 mb-1">
                Opción B — Si tu plantilla de Supabase Auth incluye código OTP de 6 dígitos, ingrésalo aquí:
              </label>
              <input
                type="text"
                required
                value={verificationCode}
                onChange={(e) => setVerificationCode(e.target.value)}
                placeholder="Código OTP recibido en tu correo"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2.5 text-white font-mono text-base tracking-widest"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-sm flex items-center justify-center gap-2 cursor-pointer"
            >
              <CheckCircle2 className="w-4 h-4" />
              {loading ? 'Verificando con Supabase Auth...' : 'Verificar Código OTP en Supabase Auth'}
            </button>
          </form>
        )}

        {/* MODO 3: INICIO DE SESIÓN */}
        {mode === 'LOGIN' && (
          <form onSubmit={handleLoginSubmit} className="space-y-3.5 text-xs">
            <div>
              <label className="block text-slate-300 mb-1">Correo electrónico</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu.correo@ejemplo.pe"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2 text-white"
              />
            </div>
            <div>
              <label className="block text-slate-300 mb-1">Contraseña</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2 text-white"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-sm cursor-pointer"
            >
              {loading ? 'Iniciando sesión...' : 'Iniciar Sesión'}
            </button>
          </form>
        )}

        {/* MODO 4: CONECTAR Y EMPEZAR EN WHATSAPP */}
        {mode === 'WHATSAPP_LINK' && (
          <div className="space-y-4 text-xs">
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-emerald-300 flex items-center gap-1.5">
                  <Smartphone className="w-4 h-4" />
                  Opción A — Vincular tu WhatsApp desde esta cuenta web
                </span>
                {currentEntrepreneur?.whatsapp_linked && (
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[11px] font-semibold">
                    Vinculado ({currentEntrepreneur.phone_masked})
                  </span>
                )}
              </div>
              <p className="text-slate-300 leading-relaxed">
                Genera un código de un solo uso con vigencia de 15 minutos y envíalo por WhatsApp al número de Qullqi Rimay (Twilio Sandbox) para asociar tu teléfono a <strong>{currentEntrepreneur?.business_name}</strong>:
              </p>

              <button
                type="button"
                onClick={handleGenerateWhatsappCode}
                disabled={loading}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold flex items-center gap-1.5 cursor-pointer"
              >
                <Link2 className="w-4 h-4" />
                Generar código único VINC-XXXXXX
              </button>

              {linkCodeData && (
                <div className="bg-emerald-950/50 border border-emerald-500/40 rounded-xl p-3 space-y-2 mt-2">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-300">Tu código único (15 min):</span>
                    <span className="font-mono text-base font-bold text-emerald-300">
                      {linkCodeData.link_code}
                    </span>
                  </div>
                  <p className="text-slate-300">{linkCodeData.sandbox_instructions}</p>
                </div>
              )}
            </div>

            <form
              onSubmit={handleClaimProvisionalInLoggedAccount}
              className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-2.5"
            >
              <span className="font-semibold text-amber-300 block">
                Opción B — ¿Empezaste el registro en WhatsApp y recibiste un código WA-LINK-XXXXXXXX?
              </span>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={claimCodeInput}
                  onChange={(e) => setClaimCodeInput(e.target.value.toUpperCase())}
                  placeholder="WA-LINK-XXXXXXXX"
                  className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold cursor-pointer"
                >
                  Vincular Ahora
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};

