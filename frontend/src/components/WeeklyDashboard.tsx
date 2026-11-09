import React, { useMemo, useState } from 'react';
import {
  ArrowDownRight,
  ArrowUpRight,
  Calculator,
  CheckCircle2,
  Filter,
  PlusCircle,
  Search,
  Wallet,
  XCircle,
} from 'lucide-react';
import { MovementRecord, MovementStatus, MovementType, WeeklySummaryItem } from '../types';

interface Props {
  weekSummary: WeeklySummaryItem;
  allMovements: MovementRecord[];
  entrepreneurName?: string;
  onCreateMovement: (payload: {
    week_number: number;
    movement_type: MovementType;
    amount_pen: number;
    category: string;
    description: string;
    auto_confirm: boolean;
  }) => Promise<void>;
  onConfirmMovement: (id: string) => Promise<void>;
  onDiscardMovement: (id: string) => Promise<void>;
}

const STANDARD_CATEGORIES = [
  'Ventas de frutas',
  'Compra de mercadería',
  'Transporte',
  'Empaques',
  'Gastos del puesto',
  'Mermas',
];

export const WeeklyDashboard: React.FC<Props> = ({
  weekSummary,
  allMovements,
  entrepreneurName = 'Rosa',
  onCreateMovement,
  onConfirmMovement,
  onDiscardMovement,
}) => {
  const [mType, setMType] = useState<MovementType>('VENTA');
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('Ventas de frutas');
  const [description, setDescription] = useState('');
  const [showManualForm, setShowManualForm] = useState(false);

  // Filtros de la tabla de movimientos (Prioridad 4)
  const [scopeMode, setScopeMode] = useState<'SELECTED_WEEK' | 'ALL_WEEKS'>('SELECTED_WEEK');
  const [filterType, setFilterType] = useState<'ALL' | MovementType>('ALL');
  const [filterCategory, setFilterCategory] = useState<string>('ALL');
  const [filterStatus, setFilterStatus] = useState<'ALL' | MovementStatus>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const availableCategories = useMemo(() => {
    const set = new Set<string>(STANDARD_CATEGORIES);
    allMovements.forEach((m) => {
      if (m.category) set.add(m.category);
    });
    return Array.from(set);
  }, [allMovements]);

  const filteredMovements = useMemo(() => {
    return allMovements.filter((m) => {
      if (scopeMode === 'SELECTED_WEEK' && m.week_number !== weekSummary.week_number) {
        return false;
      }
      if (filterType !== 'ALL' && m.movement_type !== filterType) {
        return false;
      }
      if (filterCategory !== 'ALL' && m.category !== filterCategory) {
        return false;
      }
      if (filterStatus !== 'ALL' && m.status !== filterStatus) {
        return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const hay = `${m.description} ${m.category} ${m.raw_message}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [
    allMovements,
    scopeMode,
    weekSummary.week_number,
    filterType,
    filterCategory,
    filterStatus,
    searchQuery,
  ]);

  const handleManualSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const num = parseFloat(amount);
    if (isNaN(num) || num <= 0 || !description.trim()) return;
    await onCreateMovement({
      week_number: weekSummary.week_number,
      movement_type: mType,
      amount_pen: num,
      category,
      description: description.trim(),
      auto_confirm: false,
    });
    setAmount('');
    setDescription('');
    setShowManualForm(false);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
            <Calculator className="w-4 h-4" />
            Resumen Calculado con Python • {weekSummary.week_label}
          </span>
          <h3 className="text-base font-bold text-white mt-0.5">
            Detalle de Ventas, Gastos y Tabla Filtrable de Movimientos
          </h3>
        </div>
        <button
          type="button"
          onClick={() => setShowManualForm((v) => !v)}
          className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-emerald-300 border border-slate-700 flex items-center gap-1.5 cursor-pointer"
        >
          <PlusCircle className="w-4 h-4" />
          {showManualForm ? 'Cerrar formulario web' : 'Registrar operación web'}
        </button>
      </div>

      {/* Formulario manual desde la web */}
      {showManualForm && (
        <form
          onSubmit={handleManualSubmit}
          className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 grid grid-cols-1 sm:grid-cols-4 gap-2.5 text-xs"
        >
          <div>
            <label className="block text-slate-400 mb-1">Tipo</label>
            <select
              value={mType}
              onChange={(e) => {
                const val = e.target.value as MovementType;
                setMType(val);
                setCategory(
                  val === 'VENTA' ? 'Ventas de frutas' : 'Compra de mercadería'
                );
              }}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white"
            >
              <option value="VENTA">VENTA (+)</option>
              <option value="GASTO">GASTO (-)</option>
            </select>
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Monto (S/)</label>
            <input
              type="number"
              step="0.50"
              min="1"
              required
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Ej. 120.00"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white"
            />
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Categoría</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white"
            >
              {availableCategories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-slate-400 mb-1">Descripción</label>
            <div className="flex gap-1.5">
              <input
                type="text"
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Ej. Venta de granadilla"
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white"
              />
              <button
                type="submit"
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold shrink-0 cursor-pointer"
              >
                Crear Borrador
              </button>
            </div>
          </div>
        </form>
      )}

      {/* 3 Tarjetas numéricas calculadas por Python */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Ventas Confirmadas (Sem {weekSummary.week_number})</span>
            <ArrowUpRight className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-emerald-400 mt-1">
            S/ {weekSummary.total_sales_pen.toFixed(2)}
          </div>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Gastos Confirmados (Sem {weekSummary.week_number})</span>
            <ArrowDownRight className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-xl font-bold text-rose-400 mt-1">
            S/ {weekSummary.total_expenses_pen.toFixed(2)}
          </div>
        </div>

        <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Ganancia Libre (Meta S/ {weekSummary.weekly_target_pen})</span>
            <Wallet className="w-4 h-4 text-amber-300" />
          </div>
          <div className="text-xl font-bold text-white mt-1 flex items-baseline gap-2">
            <span>S/ {weekSummary.net_margin_pen.toFixed(2)}</span>
            <span className="text-xs font-normal text-slate-400">
              ({weekSummary.profit_margin_pct}% margen)
            </span>
          </div>
        </div>
      </div>

      {/* Explicación en español sencillo de la semana */}
      <div className="bg-slate-950/90 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 leading-relaxed">
        <strong className="text-emerald-300">
          ¿Qué significa este resultado para {entrepreneurName}?{' '}
        </strong>
        {weekSummary.plain_spanish_explanation}
      </div>

      {/* Controles de filtrado y búsqueda de movimientos */}
      <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-3 space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
            <Filter className="w-3.5 h-3.5 text-emerald-400" />
            <span>
              Mostrando {filteredMovements.length} de {allMovements.length} movimientos totales
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setScopeMode('SELECTED_WEEK')}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer ${
                scopeMode === 'SELECTED_WEEK'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-900 text-slate-400 border border-slate-800'
              }`}
            >
              Solo Semana {weekSummary.week_number}
            </button>
            <button
              type="button"
              onClick={() => setScopeMode('ALL_WEEKS')}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold cursor-pointer ${
                scopeMode === 'ALL_WEEKS'
                  ? 'bg-emerald-600 text-white'
                  : 'bg-slate-900 text-slate-400 border border-slate-800'
              }`}
            >
              Todas las 8 Semanas ({allMovements.length})
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 text-xs">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar producto, flete, jaba..."
              className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-2.5 py-1.5 text-white placeholder-slate-500"
            />
          </div>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as 'ALL' | MovementType)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200"
          >
            <option value="ALL">Tipo: Ventas y Gastos</option>
            <option value="VENTA">Solo Ventas (+)</option>
            <option value="GASTO">Solo Gastos (-)</option>
          </select>

          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200"
          >
            <option value="ALL">Categoría: Todas</option>
            {availableCategories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as 'ALL' | MovementStatus)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200"
          >
            <option value="ALL">Estado: Todos</option>
            <option value="CONFIRMADO">Confirmados</option>
            <option value="PENDIENTE">Pendientes de confirmar</option>
            <option value="DESCARTADO">Descartados</option>
          </select>
        </div>
      </div>

      {/* Tabla de movimientos filtrados */}
      <div>
        {filteredMovements.length === 0 ? (
          <div className="text-center py-6 bg-slate-950/50 border border-dashed border-slate-800 rounded-xl text-xs text-slate-400">
            No hay movimientos que coincidan con el filtro actual. Usa el Simulador de WhatsApp
            o cambia a &ldquo;Todas las 8 Semanas&rdquo;.
          </div>
        ) : (
          <div className="space-y-2 max-h-[340px] overflow-y-auto pr-1">
            {filteredMovements.map((m) => (
              <div
                key={m.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs"
              >
                <div className="space-y-0.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold text-[10px]">
                      Sem {m.week_number}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                        m.movement_type === 'VENTA'
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-rose-500/20 text-rose-300'
                      }`}
                    >
                      {m.movement_type}
                    </span>
                    <span className="font-semibold text-white">
                      S/ {m.amount_pen.toFixed(2)}
                    </span>
                    <span className="text-slate-400">• {m.category}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        m.status === 'CONFIRMADO'
                          ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-700/50'
                          : m.status === 'PENDIENTE'
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : 'bg-slate-800 text-slate-400 line-through'
                      }`}
                    >
                      {m.status}
                    </span>
                    {m.created_at && (
                      <span className="text-[10px] text-slate-500">
                        {m.created_at.slice(0, 10)}
                      </span>
                    )}
                  </div>
                  <p className="text-slate-300">{m.description}</p>
                  <p className="text-[11px] text-slate-500 italic">
                    Evidencia ({m.source_channel}): &ldquo;{m.raw_message}&rdquo;
                  </p>
                </div>

                {m.status === 'PENDIENTE' && (
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={() => onConfirmMovement(m.id)}
                      className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium flex items-center gap-1 cursor-pointer"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Confirmar
                    </button>
                    <button
                      type="button"
                      onClick={() => onDiscardMovement(m.id)}
                      className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-rose-900/60 text-slate-300 flex items-center gap-1 cursor-pointer"
                    >
                      <XCircle className="w-3.5 h-3.5" />
                      Descartar
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
