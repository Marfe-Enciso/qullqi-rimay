import React, { useState } from 'react';
import {
  Award,
  BarChart3,
  CheckCircle,
  Clock,
  PieChart,
  Target,
  TrendingUp,
} from 'lucide-react';
import { EightWeekGoalSummary, EntrepreneurProfileInfo } from '../types';

interface Props {
  goal: EightWeekGoalSummary;
  entrepreneur?: EntrepreneurProfileInfo | null;
  selectedWeek: number;
  onSelectWeek: (week: number) => void;
}

export const EightWeekGoal: React.FC<Props> = ({
  goal,
  entrepreneur,
  selectedWeek,
  onSelectWeek,
}) => {
  const [showCharts, setShowCharts] = useState(true);

  const maxWeeklyAmount = Math.max(
    100,
    ...goal.weeks.map((w) => Math.max(w.total_sales_pen, w.total_expenses_pen, w.weekly_target_pen))
  );

  const normalizedCategories = (goal.category_breakdown || []).map((c) => ({
    category: c.category,
    movement_type: c.movement_type,
    total_pen: Number(c.total_pen ?? c.total_amount_pen ?? 0),
    count: Number(c.count ?? c.movements_count ?? 0),
    share_pct: Number(c.share_pct ?? c.percentage_of_type ?? 0),
  }));

  const expenseCategories = normalizedCategories.filter(
    (c) => c.movement_type === 'GASTO'
  );
  const salesCategories = normalizedCategories.filter(
    (c) => c.movement_type === 'VENTA'
  );

  const entrepreneurLabel = entrepreneur
    ? `${entrepreneur.full_name} • ${entrepreneur.business_name} (${entrepreneur.city})`
    : 'Rosa Quispe • Frutería La Huamanguina (Huamanga)';

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold uppercase tracking-wider">
            <Target className="w-4 h-4" />
            Meta de 8 Semanas • {entrepreneurLabel}
          </div>
          <h2 className="text-lg font-bold text-white mt-0.5">{goal.goal_title}</h2>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-right">
            <div className="text-[11px] text-slate-400">Acumulado Neto (Confirmado)</div>
            <div className="text-lg font-bold text-emerald-400">
              S/ {goal.accumulated_net_pen.toFixed(2)}{' '}
              <span className="text-xs font-normal text-slate-400">
                / S/ {goal.goal_target_pen.toFixed(2)}
              </span>
            </div>
          </div>
          <div className="bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-right">
            <div className="text-[11px] text-slate-400">Constancia</div>
            <div className="text-lg font-bold text-amber-300">
              {goal.completed_weeks_count}/{goal.total_weeks} sem ({goal.consistency_score_pct}%)
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowCharts((v) => !v)}
            className="px-3 py-2 rounded-xl bg-slate-950 hover:bg-slate-800 border border-slate-700 text-xs font-semibold text-emerald-300 flex items-center gap-1.5 cursor-pointer"
          >
            <BarChart3 className="w-4 h-4" />
            {showCharts ? 'Ocultar gráficos' : 'Ver gráficos de 8 semanas'}
          </button>
        </div>
      </div>

      {/* Barra de progreso global */}
      <div className="w-full bg-slate-950 h-4 rounded-full overflow-hidden border border-slate-800">
        <div
          className={`h-full transition-all duration-500 ${
            goal.goal_achieved
              ? 'bg-gradient-to-r from-emerald-500 to-teal-300'
              : 'bg-gradient-to-r from-emerald-600 to-amber-400'
          }`}
          style={{ width: `${Math.min(100, goal.progress_pct)}%` }}
        />
      </div>

      {/* Explicación en español sencillo */}
      <div className="bg-emerald-950/40 border border-emerald-500/30 rounded-xl p-3.5 flex items-start gap-3">
        <Award className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        <div className="text-sm text-emerald-100 leading-relaxed">
          <span className="font-semibold text-emerald-300">
            Explicación en sencillo:{' '}
          </span>
          {goal.plain_spanish_coaching}
        </div>
      </div>

      {/* Selector visual de las 8 semanas */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
        {goal.weeks.map((wk) => {
          const isSelected = wk.week_number === selectedWeek;
          const isLiveWeek = wk.week_number === goal.active_week_number;
          return (
            <button
              key={wk.week_number}
              type="button"
              onClick={() => onSelectWeek(wk.week_number)}
              className={`p-2.5 rounded-xl border text-left transition cursor-pointer ${
                isSelected
                  ? 'bg-emerald-900/40 border-emerald-400 ring-1 ring-emerald-400'
                  : 'bg-slate-950/80 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-semibold mb-1">
                <span className={isLiveWeek ? 'text-amber-300' : 'text-slate-200'}>
                  Sem {wk.week_number}
                </span>
                {wk.target_achieved ? (
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                ) : isLiveWeek ? (
                  <Clock className="w-3.5 h-3.5 text-amber-400" />
                ) : (
                  <TrendingUp className="w-3.5 h-3.5 text-sky-400" />
                )}
              </div>
              <div className="text-xs font-bold text-white">
                S/ {wk.net_margin_pen.toFixed(0)}
              </div>
              <div className="text-[10px] text-slate-400 truncate">
                {isLiveWeek && wk.confirmed_movements_count === 0
                  ? 'En vivo (Interactiva)'
                  : `${wk.confirmed_movements_count} mov.`}
              </div>
            </button>
          );
        })}
      </div>

      {/* Gráficos de Evolución Semanal y Gastos por Categoría (Prioridad 4) */}
      {showCharts && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 pt-2 border-t border-slate-800">
          {/* Evolución Semanal: Ventas vs Gastos vs Margen Neto */}
          <div className="lg:col-span-7 bg-slate-950 border border-slate-800 rounded-xl p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <BarChart3 className="w-4 h-4 text-emerald-400" />
                Evolución Semanal (Ventas vs. Gastos vs. Neto)
              </span>
              <div className="flex items-center gap-3 text-[11px] text-slate-400">
                <span className="inline-flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-xs bg-emerald-500 inline-block" /> Ventas
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-xs bg-rose-500/80 inline-block" /> Gastos
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded-xs bg-amber-400 inline-block" /> Neto Libre
                </span>
              </div>
            </div>

            <div className="space-y-2">
              {goal.weeks.map((wk) => {
                const salesPct = Math.min(100, (wk.total_sales_pen / maxWeeklyAmount) * 100);
                const expPct = Math.min(100, (wk.total_expenses_pen / maxWeeklyAmount) * 100);
                const netPct = Math.min(
                  100,
                  (Math.max(0, wk.net_margin_pen) / maxWeeklyAmount) * 100
                );
                return (
                  <div
                    key={wk.week_number}
                    onClick={() => onSelectWeek(wk.week_number)}
                    className={`p-2 rounded-lg border transition cursor-pointer ${
                      wk.week_number === selectedWeek
                        ? 'bg-slate-900 border-emerald-500/50'
                        : 'bg-slate-950 border-slate-900 hover:border-slate-800'
                    }`}
                  >
                    <div className="flex items-center justify-between text-[11px] mb-1">
                      <span className="font-semibold text-slate-200">{wk.week_label}</span>
                      <span className="text-slate-400">
                        Ventas{' '}
                        <strong className="text-emerald-400">
                          S/ {wk.total_sales_pen.toFixed(0)}
                        </strong>{' '}
                        • Gastos{' '}
                        <strong className="text-rose-400">
                          S/ {wk.total_expenses_pen.toFixed(0)}
                        </strong>{' '}
                        • Neto{' '}
                        <strong className="text-amber-300">
                          S/ {wk.net_margin_pen.toFixed(0)}
                        </strong>
                      </span>
                    </div>
                    <div className="space-y-1">
                      <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden">
                        <div
                          className="bg-emerald-500 h-full rounded-full"
                          style={{ width: `${salesPct}%` }}
                        />
                      </div>
                      <div className="w-full bg-slate-900 h-1.5 rounded-full overflow-hidden flex gap-0.5">
                        <div
                          className="bg-rose-500/80 h-full rounded-full"
                          style={{ width: `${expPct}%` }}
                        />
                        <div
                          className="bg-amber-400 h-full rounded-full"
                          style={{ width: `${netPct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Gastos e Ingresos por Categoría */}
          <div className="lg:col-span-5 bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                  <PieChart className="w-4 h-4 text-amber-400" />
                  Gastos por Categoría (Confirmados)
                </span>
                <span className="text-[11px] text-slate-400">
                  {expenseCategories.reduce((acc, c) => acc + c.count, 0)} registros de gasto
                </span>
              </div>

              {expenseCategories.length === 0 ? (
                <p className="text-xs text-slate-500 py-6 text-center">
                  Aún no hay gastos confirmados para desglosar por categoría.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {expenseCategories.map((cat) => (
                    <div key={`${cat.movement_type}-${cat.category}`} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-200 font-medium">
                          {cat.category}{' '}
                          <span className="text-[11px] text-slate-500">({cat.count} mov.)</span>
                        </span>
                        <span className="text-rose-300 font-semibold">
                          S/ {cat.total_pen.toFixed(2)}{' '}
                          <span className="text-[10px] text-slate-400">({cat.share_pct}%)</span>
                        </span>
                      </div>
                      <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-rose-500 to-amber-500 h-full rounded-full"
                          style={{ width: `${Math.min(100, cat.share_pct)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {salesCategories.length > 0 && (
              <div className="mt-4 pt-3 border-t border-slate-800/80">
                <div className="text-[11px] text-slate-400 mb-1.5">Ingresos por Categoría:</div>
                {salesCategories.map((sc) => (
                  <div
                    key={sc.category}
                    className="flex items-center justify-between text-xs bg-emerald-950/30 border border-emerald-500/20 rounded-lg px-3 py-1.5"
                  >
                    <span className="text-emerald-200 font-medium">
                      {sc.category} ({sc.count} ventas)
                    </span>
                    <span className="text-emerald-400 font-bold">
                      S/ {sc.total_pen.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
