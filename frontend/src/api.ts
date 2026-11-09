import {
  AuthRegisterRequest,
  AuthRegisterResponse,
  AuthSessionResponse,
  ChatMessageBubble,
  ConsentRecord,
  EightWeekGoalSummary,
  EntrepreneurProfileInfo,
  FinancialProfileReport,
  LanguageCode,
  MovementRecord,
  MovementType,
  SimulatorMessageResponse,
  WhatsappLinkGenerateResponse,
  WhatsappProvisionalInspect,
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
const SESSION_TOKEN_STORAGE_KEY = 'qullqi_rimay_auth_jwt';

let currentSupabaseJwt: string | null = (() => {
  try {
    return window.localStorage.getItem(SESSION_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
})();

function getOrCreateVisitorSandboxId(): string {
  const storageKey = 'qullqi_demo_visitor_id';
  try {
    const existing = window.sessionStorage.getItem(storageKey);
    if (existing && /^[a-zA-Z0-9_-]{8,64}$/.test(existing)) {
      return existing;
    }
    const generated = `vis-${crypto.randomUUID().replace(/[^a-zA-Z0-9]/g, '').slice(0, 20)}`;
    window.sessionStorage.setItem(storageKey, generated);
    return generated;
  } catch {
    return 'vis-public-hackathon-demo';
  }
}

async function requestJson<T>(
  path: string,
  options?: RequestInit,
  forceDirectApi = false
): Promise<T> {
  const isAuthenticated = Boolean(currentSupabaseJwt);
  const routePrefix = forceDirectApi || isAuthenticated ? '' : '/demo-sandbox';
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options?.headers as Record<string, string>) || {}),
  };

  if (currentSupabaseJwt) {
    headers['Authorization'] = `Bearer ${currentSupabaseJwt}`;
  } else {
    headers['X-Demo-Visitor-Id'] = getOrCreateVisitorSandboxId();
  }

  const res = await fetch(`${API_BASE}${routePrefix}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errBody.detail || `Error HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  setSupabaseAuthToken: (jwt: string | null) => {
    currentSupabaseJwt = jwt ? jwt.trim() : null;
    try {
      if (currentSupabaseJwt) {
        window.localStorage.setItem(SESSION_TOKEN_STORAGE_KEY, currentSupabaseJwt);
      } else {
        window.localStorage.removeItem(SESSION_TOKEN_STORAGE_KEY);
      }
    } catch {
      // Ignore localStorage errors
    }
  },
  isAuthenticatedMode: () => Boolean(currentSupabaseJwt),

  // --- Registro Web Real, Verificación de Correo, Login y Vinculación WhatsApp ---
  registerAccount: (payload: AuthRegisterRequest) =>
    requestJson<AuthRegisterResponse>(
      '/auth/register',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      true
    ),
  verifyEmailAndActivate: (email: string, verification_code: string) =>
    requestJson<AuthSessionResponse>(
      '/auth/verify-email',
      {
        method: 'POST',
        body: JSON.stringify({ email, verification_code }),
      },
      true
    ),
  loginAccount: (email: string, password: string) =>
    requestJson<AuthSessionResponse>(
      '/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      },
      true
    ),
  getAuthenticatedProfile: () =>
    requestJson<EntrepreneurProfileInfo>('/auth/me', undefined, true),
  getSandboxEntrepreneur: () =>
    requestJson<EntrepreneurProfileInfo>('/entrepreneur'),
  updateLanguagePreference: (preferred_language: LanguageCode) =>
    currentSupabaseJwt
      ? requestJson<EntrepreneurProfileInfo>(
          '/auth/preferences',
          {
            method: 'PATCH',
            body: JSON.stringify({ preferred_language }),
          },
          true
        )
      : requestJson<EntrepreneurProfileInfo>('/preferences', {
          method: 'PATCH',
          body: JSON.stringify({ preferred_language }),
        }),
  generateWhatsappLinkCode: () =>
    requestJson<WhatsappLinkGenerateResponse>(
      '/auth/whatsapp/generate-code',
      { method: 'POST' },
      true
    ),
  claimWhatsappProvisional: (claim_code: string) =>
    requestJson<EntrepreneurProfileInfo>(
      '/auth/whatsapp/claim-provisional',
      {
        method: 'POST',
        body: JSON.stringify({ claim_code }),
      },
      true
    ),
  inspectWhatsappProvisional: (claimCode: string) =>
    requestJson<WhatsappProvisionalInspect>(
      `/auth/whatsapp/provisional/${encodeURIComponent(claimCode)}`,
      undefined,
      true
    ),

  // --- Operaciones del Negocio (Modo Autenticado o Modo Demo Ficticio Rosa) ---
  getGoalSummary: () => requestJson<EightWeekGoalSummary>('/analytics/goal'),
  getMovements: (weekNumber?: number) =>
    requestJson<MovementRecord[]>(
      weekNumber ? `/movements?week_number=${weekNumber}` : '/movements'
    ),
  createManualMovement: (payload: {
    week_number: number;
    movement_type: MovementType;
    amount_pen: number;
    category: string;
    description: string;
    auto_confirm?: boolean;
  }) =>
    requestJson<MovementRecord>('/movements', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  confirmMovement: (movementId: string) =>
    requestJson<MovementRecord>(`/movements/${movementId}/confirm`, {
      method: 'POST',
    }),
  discardMovement: (movementId: string) =>
    requestJson<MovementRecord>(`/movements/${movementId}/discard`, {
      method: 'POST',
    }),
  getChatHistory: () => requestJson<ChatMessageBubble[]>('/simulator/history'),
  sendWhatsAppMessage: (message: string, weekNumber = 8) =>
    requestJson<SimulatorMessageResponse>('/simulator/message', {
      method: 'POST',
      body: JSON.stringify({ message, week_number: weekNumber }),
    }),
  getFinancialProfile: () => requestJson<FinancialProfileReport>('/profile'),
  listConsents: () => requestJson<ConsentRecord[]>('/consents'),
  grantConsent: (recipient_entity: string, purpose: string, accepted_terms: boolean) =>
    requestJson<ConsentRecord>('/consents/grant', {
      method: 'POST',
      body: JSON.stringify({ recipient_entity, purpose, accepted_terms }),
    }),
  revokeConsent: (consentId: string, reason: string) =>
    requestJson<ConsentRecord>(`/consents/${consentId}/revoke`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  inspectSharedToken: (shareToken: string) =>
    requestJson<{ consent: ConsentRecord; shared_profile: FinancialProfileReport }>(
      `/consents/shared/${shareToken}`
    ),
  resetDemo: () =>
    requestJson<{ status: string; message: string }>('/reset', {
      method: 'POST',
    }),
};
