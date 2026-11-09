import React, { useState } from 'react';
import {
  CheckCircle2,
  Code2,
  Globe,
  MessageSquare,
  Send,
  Sparkles,
  XCircle,
} from 'lucide-react';
import { ChatMessageBubble, LanguageCode, MovementRecord } from '../types';

interface Props {
  chatHistory: ChatMessageBubble[];
  pendingMovements: MovementRecord[];
  activeWeek: number;
  preferredLanguage?: LanguageCode;
  entrepreneurName?: string;
  isSending: boolean;
  onSendMessage: (message: string) => Promise<void>;
  onConfirmMovement: (id: string) => Promise<void>;
  onDiscardMovement: (id: string) => Promise<void>;
}

const DEMO_PROMPTS_ES = [
  'Vendí 20 kg de naranja a 4 y gasté 6 en pasaje',
  'Casera hoy vendí 190 soles de palta fuerte y lúcuma, y gasté 45 soles en jabas y transporte',
  'Por la tarde salieron 135 soles en chirimoya y tuna morada, y pagué 25 soles de flete',
  'Sí confirmo',
  '¿Cómo voy con mi meta?',
];

const DEMO_PROMPTS_QU = [
  'Rantikurqani 120 soles papata hinaspa gastarqani 20 soles pasajepi',
  'Kunan punchaw rantikurqani 95 soles palta, gastarqani 15 soles bolsaspi',
  'Ari takyachini',
  'Haykataq qullqi yupayniypi (Willakuy)',
  'Kunan punchaw 80 qullqi ruru', // Ejemplo ambiguo para demostrar aclaración obligatoria
];

export const WhatsAppSimulator: React.FC<Props> = ({
  chatHistory,
  pendingMovements,
  activeWeek,
  preferredLanguage = 'es',
  entrepreneurName = 'Rosa Quispe',
  isSending,
  onSendMessage,
  onConfirmMovement,
  onDiscardMovement,
}) => {
  const [input, setInput] = useState('');
  const [showJsonIds, setShowJsonIds] = useState<Record<string, boolean>>({});

  const activePrompts = preferredLanguage === 'qu' ? DEMO_PROMPTS_QU : DEMO_PROMPTS_ES;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isSending) return;
    const text = input.trim();
    setInput('');
    await onSendMessage(text);
  };

  const toggleJson = (id: string) => {
    setShowJsonIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 border border-emerald-500/30 rounded-2xl overflow-hidden shadow-xl">
      {/* Cabecera estilo WhatsApp */}
      <div className="bg-emerald-900/80 px-4 py-3 border-b border-emerald-700/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-emerald-500 flex items-center justify-center text-slate-950 font-bold shadow">
            QR
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="font-semibold text-white text-sm">
                Qullqi Rimay • WhatsApp
              </h2>
              <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-400/20 text-emerald-300 border border-emerald-400/30">
                Semana {activeWeek}
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-400/20 text-amber-200 border border-amber-400/30 inline-flex items-center gap-1">
                <Globe className="w-3 h-3" />
                {preferredLanguage === 'qu' ? 'Quechua Ayacuchano (Chanka)' : 'Español'}
              </span>
            </div>
            <p className="text-xs text-emerald-200/80">
              {entrepreneurName} • Confirmación obligatoria en 2 pasos activa
            </p>
          </div>
        </div>
        <MessageSquare className="w-5 h-5 text-emerald-300 shrink-0" />
      </div>

      {preferredLanguage === 'qu' && (
        <div className="bg-amber-950/60 border-b border-amber-500/30 px-3.5 py-1.5 text-[11px] text-amber-200">
          🌿 <strong>Modo Quechua Ayacuchano (Chanka):</strong> Textos sujetos a revisión lingüística. Si un mensaje es ambiguo, Qullqi Rimay solicita aclaración antes de guardar.
        </div>
      )}

      {/* Bandeja de Movimientos Pendientes de Confirmación */}
      {pendingMovements.length > 0 && (
        <div className="bg-amber-500/15 border-b border-amber-500/40 px-4 py-2.5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-semibold text-amber-300 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              {pendingMovements.length} movimiento(s) en borrador esperando confirmación:
            </span>
          </div>
          <div className="space-y-1.5">
            {pendingMovements.map((mov) => (
              <div
                key={mov.id}
                className="flex items-center justify-between bg-slate-950/80 border border-amber-500/30 rounded-lg px-3 py-1.5 text-xs"
              >
                <div>
                  <span
                    className={`font-bold mr-2 ${
                      mov.movement_type === 'VENTA' ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {mov.movement_type} S/ {mov.amount_pen.toFixed(2)}
                  </span>
                  <span className="text-slate-300">{mov.category}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => onConfirmMovement(mov.id)}
                    className="px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium flex items-center gap-1 cursor-pointer"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {preferredLanguage === 'qu' ? 'Takyachiy (Confirmar)' : 'Confirmar'}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDiscardMovement(mov.id)}
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-rose-900/60 text-slate-300 hover:text-rose-200 flex items-center gap-1 cursor-pointer"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    {preferredLanguage === 'qu' ? 'Pichay' : 'Descartar'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Historial de burbujas */}
      <div className="flex-1 p-4 space-y-3 overflow-y-auto max-h-[420px] bg-slate-950/60">
        {chatHistory.map((b) => {
          const isEntrepreneur = b.sender === 'ROSA';
          return (
            <div
              key={b.id}
              className={`flex flex-col ${isEntrepreneur ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm shadow ${
                  isEntrepreneur
                    ? 'bg-emerald-700 text-white rounded-br-xs'
                    : 'bg-slate-800 text-slate-100 border border-slate-700 rounded-bl-xs'
                }`}
              >
                <div className="text-[11px] font-semibold opacity-75 mb-0.5 flex items-center justify-between gap-4">
                  <span>
                    {isEntrepreneur ? `👩🏽‍🌾 ${entrepreneurName}` : '🤖 Qullqi Rimay IA'}
                  </span>
                  <span>Semana {b.week_number}</span>
                </div>
                <p className="leading-relaxed whitespace-pre-wrap">{b.text}</p>

                {b.structured_json && (
                  <div className="mt-2 pt-2 border-t border-slate-700/80">
                    <button
                      type="button"
                      onClick={() => toggleJson(b.id)}
                      className="text-[11px] text-emerald-300 hover:text-emerald-200 flex items-center gap-1 cursor-pointer"
                    >
                      <Code2 className="w-3.5 h-3.5" />
                      {showJsonIds[b.id]
                        ? 'Ocultar JSON estructurado IA'
                        : `Ver JSON estructurado (${b.structured_json.detected_intent})`}
                    </button>
                    {showJsonIds[b.id] && (
                      <pre className="mt-1.5 p-2 rounded bg-slate-950 text-[11px] text-emerald-300 overflow-x-auto border border-slate-800">
                        {JSON.stringify(b.structured_json, null, 2)}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Sugerencias rápidas bilingües */}
      <div className="px-3 py-2 bg-slate-900 border-t border-slate-800">
        <p className="text-[11px] text-slate-400 mb-1.5">
          💬 Ejemplos rápidos en{' '}
          <strong>
            {preferredLanguage === 'qu' ? 'Quechua Ayacuchano (Chanka)' : 'Español'}
          </strong>{' '}
          (Semana {activeWeek}):
        </p>
        <div className="flex flex-wrap gap-1.5">
          {activePrompts.map((prompt, idx) => (
            <button
              key={idx}
              type="button"
              disabled={isSending}
              onClick={() => onSendMessage(prompt)}
              className="text-left text-[11px] px-2.5 py-1 rounded-full bg-slate-800 hover:bg-emerald-900/50 text-emerald-200 border border-slate-700 hover:border-emerald-500/40 transition cursor-pointer"
            >
              {prompt.length > 56 ? `${prompt.slice(0, 56)}…` : prompt}
            </button>
          ))}
        </div>
      </div>

      {/* Caja de texto */}
      <form
        onSubmit={handleSubmit}
        className="p-3 bg-slate-900 border-t border-slate-800 flex items-center gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            preferredLanguage === 'qu'
              ? 'Qillqamuy (ej: Rantikurqani 120 soles papata)...'
              : 'Escribe tu venta o gasto (ej: Vendí 180 soles de palta y gasté 40 en jabas)...'
          }
          className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
        />
        <button
          type="submit"
          disabled={isSending || !input.trim()}
          className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white font-medium text-sm flex items-center gap-1.5 cursor-pointer"
        >
          <Send className="w-4 h-4" />
          {preferredLanguage === 'qu' ? 'Apachiy' : 'Enviar'}
        </button>
      </form>
    </div>
  );
};
