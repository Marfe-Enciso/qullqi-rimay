import React, { useCallback, useEffect, useState } from 'react';
import { api } from './api';
import {
  ChatMessageBubble,
  ConsentRecord,
  EightWeekGoalSummary,
  EntrepreneurProfileInfo,
  FinancialProfileReport,
  LanguageCode,
  MovementRecord,
  MovementType,
} from './types';
import { AuthAndWhatsappModal } from './components/AuthAndWhatsappModal';
import { EightWeekGoal } from './components/EightWeekGoal';
import { FinancialProfileModal } from './components/FinancialProfileModal';
import { WeeklyDashboard } from './components/WeeklyDashboard';
import { WhatsAppSimulator } from './components/WhatsAppSimulator';
import { DashboardLayout } from './DashboardLayout';

export const App: React.FC = () => {
  const [entrepreneur, setEntrepreneur] = useState<EntrepreneurProfileInfo | null>(null);
  const [goal, setGoal] = useState<EightWeekGoalSummary | null>(null);
  const [movements, setMovements] = useState<MovementRecord[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatMessageBubble[]>([]);
  const [profile, setProfile] = useState<FinancialProfileReport | null>(null);
  const [consents, setConsents] = useState<ConsentRecord[]>([]);
  const [selectedWeek, setSelectedWeek] = useState<number>(8);
  const [activeTab, setActiveTab] = useState<'DASHBOARD' | 'PROFILE'>('DASHBOARD');
  const [isSending, setIsSending] = useState(false);
  const [sharedPreviewStatus, setSharedPreviewStatus] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // Estado del Modal de Registro / Login / Vinculación WhatsApp
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<
    'REGISTER' | 'LOGIN' | 'VERIFY_EMAIL' | 'WHATSAPP_LINK'
  >('REGISTER');
  const [urlClaimCode, setUrlClaimCode] = useState<string | null>(null);

  const isAuthenticatedAccount = api.isAuthenticatedMode();

  const loadAllState = useCallback(async () => {
    try {
      setErrorBanner(null);
      const [entData, goalData, movData, chatData, profData, consentData] =
        await Promise.all([
          api.isAuthenticatedMode()
            ? api.getAuthenticatedProfile()
            : api.getSandboxEntrepreneur(),
          api.getGoalSummary(),
          api.getMovements(),
          api.getChatHistory(),
          api.getFinancialProfile(),
          api.listConsents(),
        ]);
      setEntrepreneur(entData);
      setGoal(goalData);
      setMovements(movData);
      setChatHistory(chatData);
      setProfile(profData);
      setConsents(consentData);
    } catch (err: unknown) {
      if (api.isAuthenticatedMode()) {
        // Si el token guardado expiró tras reinicio, volver al modo demo sin bloquear la pantalla
        api.setSupabaseAuthToken(null);
      }
      setErrorBanner(
        err instanceof Error
          ? err.message
          : 'No se pudo conectar con el backend FastAPI en /api'
      );
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const claimParam = params.get('wa_claim');
    if (claimParam && claimParam.trim()) {
      setUrlClaimCode(claimParam.trim().toUpperCase());
      setAuthModalMode('REGISTER');
      setAuthModalOpen(true);
    }
    void loadAllState();
  }, [loadAllState]);

  const handleAuthenticatedSuccess = async (ent: EntrepreneurProfileInfo) => {
    setEntrepreneur(ent);
    setSelectedWeek(ent.active_week || 1);
    await loadAllState();
  };

  const handleSwitchToFictionalDemo = async () => {
    api.setSupabaseAuthToken(null);
    setSelectedWeek(8);
    setSharedPreviewStatus(null);
    await loadAllState();
  };

  const handleLanguageChange = async (newLang: LanguageCode) => {
    try {
      const updated = await api.updateLanguagePreference(newLang);
      setEntrepreneur(updated);
      await loadAllState();
    } catch (err: unknown) {
      setErrorBanner(
        err instanceof Error ? err.message : 'No se pudo cambiar el idioma'
      );
    }
  };

  const handleSendMessage = async (text: string) => {
    setIsSending(true);
    try {
      await api.sendWhatsAppMessage(text, selectedWeek);
      await loadAllState();
    } catch (err: unknown) {
      setErrorBanner(err instanceof Error ? err.message : 'Error al enviar mensaje');
    } finally {
      setIsSending(false);
    }
  };

  const handleConfirmMovement = async (id: string) => {
    await api.confirmMovement(id);
    await loadAllState();
  };

  const handleDiscardMovement = async (id: string) => {
    await api.discardMovement(id);
    await loadAllState();
  };

  const handleCreateManualMovement = async (payload: {
    week_number: number;
    movement_type: MovementType;
    amount_pen: number;
    category: string;
    description: string;
    auto_confirm: boolean;
  }) => {
    await api.createManualMovement(payload);
    await loadAllState();
  };

  const handleGrantConsent = async (
    recipient: string,
    purpose: string,
    acceptedTerms: boolean
  ) => {
    const created = await api.grantConsent(recipient, purpose, acceptedTerms);
    setSharedPreviewStatus(
      `✅ Consentimiento ACTIVO creado (Token: ${created.share_token}).`
    );
    await loadAllState();
  };

  const handleRevokeConsent = async (consentId: string, reason: string) => {
    const revoked = await api.revokeConsent(consentId, reason);
    setSharedPreviewStatus(
      `🛑 Consentimiento ${revoked.id} REVOCADO. Cualquier consulta externa al token fue bloqueada.`
    );
    await loadAllState();
  };

  const handleInspectToken = async (shareToken: string) => {
    try {
      const res = await api.inspectSharedToken(shareToken);
      setSharedPreviewStatus(
        `🔍 Enlace ACTIVO verificado: Permite ver ${res.shared_profile.verified_weeks_count}/8 semanas (Hash: ${res.shared_profile.evidence_integrity_hash.slice(
          0,
          14
        )}…).`
      );
    } catch (err: unknown) {
      setSharedPreviewStatus(
        `🚫 Acceso bloqueado al token (${shareToken}): ${
          err instanceof Error ? err.message : 'Revocado'
        }`
      );
    }
  };

  const handleResetDemo = async () => {
    await api.resetDemo();
    setSelectedWeek(8);
    setSharedPreviewStatus(null);
    await loadAllState();
  };

  const pendingMovements = movements.filter((m) => m.status === 'PENDIENTE');
  const currentWeekSummary =
    goal?.weeks.find((w) => w.week_number === selectedWeek) ||
    goal?.weeks[(entrepreneur?.active_week || 8) - 1] ||
    goal?.weeks[0];

  const activeLang: LanguageCode = entrepreneur?.preferred_language || 'es';

  return (
    <>
      <DashboardLayout
        entrepreneur={entrepreneur} goal={goal} week={currentWeekSummary}
        authenticated={isAuthenticatedAccount} activeTab={activeTab} language={activeLang}
        onTab={setActiveTab} onLanguage={handleLanguageChange}
        onRegister={() => { setAuthModalMode('REGISTER'); setAuthModalOpen(true); }}
        onLogin={() => { setAuthModalMode('LOGIN'); setAuthModalOpen(true); }}
        onWhatsapp={() => { setAuthModalMode('WHATSAPP_LINK'); setAuthModalOpen(true); }}
        onLogout={handleSwitchToFictionalDemo} onReset={handleResetDemo}
      >
        {errorBanner && <div className="notice-error" role="alert">⚠️ {errorBanner}</div>}
        {goal && <section id="progreso" className="content-section"><EightWeekGoal goal={goal} entrepreneur={entrepreneur} selectedWeek={selectedWeek} onSelectWeek={(wk) => setSelectedWeek(wk)} /></section>}
        {activeTab === 'DASHBOARD' ? (
          <div className="workspace-lower">
            <section id="movimientos" className="content-section">
              {currentWeekSummary && <WeeklyDashboard weekSummary={currentWeekSummary} allMovements={movements} entrepreneurName={entrepreneur?.full_name.split(' ')[0] || 'Rosa'} onCreateMovement={handleCreateManualMovement} onConfirmMovement={handleConfirmMovement} onDiscardMovement={handleDiscardMovement} />}
            </section>
            <section id="conversacion" className="content-section">
              <WhatsAppSimulator chatHistory={chatHistory} pendingMovements={pendingMovements} activeWeek={selectedWeek} preferredLanguage={activeLang} entrepreneurName={entrepreneur?.full_name || 'Rosa Quispe'} isSending={isSending} onSendMessage={handleSendMessage} onConfirmMovement={handleConfirmMovement} onDiscardMovement={handleDiscardMovement} />
            </section>
          </div>
        ) : profile && <section id="perfil" className="content-section"><FinancialProfileModal profile={profile} consents={consents} onGrantConsent={handleGrantConsent} onRevokeConsent={handleRevokeConsent} onInspectToken={handleInspectToken} sharedPreviewStatus={sharedPreviewStatus} /></section>}
      </DashboardLayout>
      <AuthAndWhatsappModal isOpen={authModalOpen} initialMode={authModalMode} initialClaimCode={urlClaimCode} currentEntrepreneur={entrepreneur} onClose={() => setAuthModalOpen(false)} onAuthenticated={handleAuthenticatedSuccess} />
    </>
  );
};

export default App;