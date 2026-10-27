import React from 'react';
import type { TravelPackage } from '../types';
import { Plane, MapPin, CheckCircle, AlertTriangle, HelpCircle, ArrowRight, Star, Calendar, ShieldAlert } from 'lucide-react';

interface PackageCardProps {
  pkg: TravelPackage;
  onSelect: (pkgId: string) => void;
  isSelected?: boolean;
}

const formatCurrency = (amount: number | string | undefined | null, curr: string) => {
  if (amount === undefined || amount === null) return '—';
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '—';
  const sym = curr === 'INR' ? '₹' : curr === 'USD' ? '$' : curr === 'EUR' ? '€' : `${curr} `;
  return `${sym}${num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
};

export const PackageCard: React.FC<PackageCardProps> = ({ pkg, onSelect, isSelected = false }) => {
  const isWithinBudget = pkg.budget_classification === 'within_budget';
  const isOverBudget = pkg.budget_classification === 'over_budget';
  const isIncomplete = pkg.budget_classification === 'incomplete';

  const outFlight = pkg.selected_outbound_flight;
  const retFlight = pkg.selected_return_flight;
  const hotel = pkg.selected_hotel;

  const totalDays = pkg.day_wise.length;

  return (
    <div
      className={`group relative rounded-3xl bg-white dark:bg-gray-800 border transition-all duration-300 flex flex-col justify-between overflow-hidden shadow-lg hover:shadow-2xl hover:-translate-y-1 ${
        isSelected
          ? 'ring-2 ring-purple-500 border-purple-500/80 dark:border-purple-500/80 shadow-purple-500/10'
          : 'border-gray-200 dark:border-gray-700/80 hover:border-purple-300 dark:hover:border-purple-700'
      }`}
    >
      {/* Top Banner & Budget Badge */}
      <div className="p-6 pb-4">
        <div className="flex items-start justify-between gap-2 mb-3 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold tracking-wide uppercase ${
                isWithinBudget
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800'
                  : isOverBudget
                  ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300 dark:border-rose-800'
                  : isIncomplete
                  ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800'
                  : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300 border border-gray-300 dark:border-gray-700'
              }`}
            >
              {isWithinBudget && <CheckCircle className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />}
              {isOverBudget && <AlertTriangle className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400" />}
              {isIncomplete && <HelpCircle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />}
              <span>
                {isWithinBudget
                  ? 'Within Budget'
                  : isOverBudget
                  ? 'Above Budget'
                  : isIncomplete
                  ? 'Incomplete Price'
                  : 'No Target Limit'}
              </span>
            </span>

            {pkg.trip_pace && (
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                  pkg.trip_pace === 'RUSHED'
                    ? 'bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300/80 dark:border-amber-700/80'
                    : pkg.trip_pace === 'SLOW'
                    ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300/80 dark:border-emerald-700/80'
                    : 'bg-blue-50 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border-blue-300/80 dark:border-blue-700/80'
                }`}
                title={pkg.pace_description || `${pkg.trip_pace} pace`}
              >
                <span>{pkg.trip_pace === 'RUSHED' ? '⚡' : pkg.trip_pace === 'SLOW' ? '🌿' : '⚖️'}</span>
                <span>{pkg.trip_pace === 'RUSHED' ? 'Rushed' : pkg.trip_pace === 'SLOW' ? 'Slow' : 'Balanced'}</span>
              </span>
            )}
            {pkg.is_complete ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 dark:border-emerald-700/80">
                <CheckCircle className="w-3 h-3 text-emerald-500" /> Complete Package
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300/80 dark:border-amber-700/80">
                <AlertTriangle className="w-3 h-3 text-amber-500" /> Partial Package
              </span>
            )}
          </div>

          {totalDays > 0 && (
            <span className="flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700/60 px-2.5 py-1 rounded-lg">
              <Calendar className="w-3 h-3 text-gray-400" />
              {totalDays} Days
            </span>
          )}
        </div>

        <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 leading-snug">
          {pkg.name}
        </h3>
        <p className="text-xs text-gray-600 dark:text-gray-400 mt-1.5 line-clamp-2 leading-relaxed">
          {pkg.description}
        </p>
        {pkg.description.includes('Focus:') && (
          <div className="mt-2.5 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-purple-50 dark:bg-purple-950/40 border border-purple-200/80 dark:border-purple-800/60 text-[11px] font-semibold text-purple-700 dark:text-purple-300 max-w-full">
            <span className="shrink-0">🎯</span>
            <span className="truncate">{pkg.description.split('Focus:')[1].trim()}</span>
          </div>
        )}

        {/* Pricing Block */}
        <div className="mt-5 p-4 rounded-2xl bg-gradient-to-br from-gray-50 to-gray-100/60 dark:from-gray-900/80 dark:to-gray-850 border border-gray-200/70 dark:border-gray-750">
          <div className="flex items-baseline justify-between">
            <div>
              <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Total Estimated Cost
              </span>
              <div className="text-2xl font-black text-gray-900 dark:text-white mt-0.5 tracking-tight">
                {pkg.total_cost ? formatCurrency(pkg.total_cost.amount, pkg.currency) : 'Price incomplete'}
              </div>
              {!pkg.total_cost && pkg.known_subtotal && (
                <div className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                  Known so far: {formatCurrency(pkg.known_subtotal.amount, pkg.known_subtotal.currency || pkg.currency)} (incomplete)
                </div>
              )}
            </div>

            <div className="text-right">
              {isWithinBudget && pkg.remaining_budget && Number(pkg.remaining_budget.amount) > 0 && (
                <div className="text-xs font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2.5 py-1 rounded-lg border border-emerald-200 dark:border-emerald-800/60">
                  {formatCurrency(pkg.remaining_budget.amount, pkg.currency)} left
                </div>
              )}
              {isOverBudget && pkg.amount_over_budget && Number(pkg.amount_over_budget.amount) > 0 && (
                <div className="text-xs font-bold text-rose-700 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 px-2.5 py-1 rounded-lg border border-rose-200 dark:border-rose-800/60">
                  +{formatCurrency(pkg.amount_over_budget.amount, pkg.currency)} over
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Key Selections Summary */}
        <div className="mt-4 space-y-2.5 text-xs">
          {/* Outbound flight */}
          <div className="flex items-center gap-2 p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-700/60">
            <div className="p-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 shrink-0">
              <Plane className="w-3.5 h-3.5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-gray-900 dark:text-gray-100 truncate">
                {outFlight ? `${outFlight.segments[0]?.airline || 'Flight'} (${outFlight.segments[0]?.departure?.code ?? '?'} → ${outFlight.segments[outFlight.segments.length - 1]?.arrival?.code ?? '?'})` : 'Outbound flight unavailable'}
              </div>
              <div className="text-[11px] text-gray-500 dark:text-gray-400 flex items-center gap-2 mt-0.5">
                {outFlight && <span>{outFlight.stops === 0 ? 'Nonstop' : `${outFlight.stops} stop`}</span>}
                {outFlight?.total_duration_minutes && <span>• {Math.floor(outFlight.total_duration_minutes / 60)}h {outFlight.total_duration_minutes % 60}m</span>}
                {outFlight?.price && <span className="font-medium text-gray-700 dark:text-gray-300">• {formatCurrency(outFlight.price.amount, outFlight.price.currency)}</span>}
              </div>
            </div>
          </div>

          {/* Return flight */}
          {retFlight ? (
            <div className="flex items-center gap-2 p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-700/60">
              <div className="p-1.5 rounded-lg bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 shrink-0">
                <Plane className="w-3.5 h-3.5 rotate-180" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-gray-900 dark:text-gray-100 truncate">
                  {retFlight.segments[0]?.airline || 'Return Flight'} ({retFlight.segments[0]?.departure?.code ?? '?'} → {retFlight.segments[retFlight.segments.length - 1]?.arrival?.code ?? '?'})
                </div>
                <div className="text-[11px] text-gray-500 dark:text-gray-400 flex items-center gap-2 mt-0.5">
                  <span>{retFlight.stops === 0 ? 'Nonstop' : `${retFlight.stops} stop`}</span>
                  {retFlight.total_duration_minutes && <span>• {Math.floor(retFlight.total_duration_minutes / 60)}h {retFlight.total_duration_minutes % 60}m</span>}
                  {retFlight.price && <span className="font-medium text-gray-700 dark:text-gray-300">• {formatCurrency(retFlight.price.amount, retFlight.price.currency)}</span>}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-700/60">
              <div className="p-1.5 rounded-lg bg-gray-200 dark:bg-gray-700 text-gray-400 shrink-0">
                <Plane className="w-3.5 h-3.5 rotate-180" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-gray-500 dark:text-gray-400 truncate">
                  Return flight unavailable
                </div>
                <div className="text-[11px] text-gray-400 mt-0.5">
                  No usable return flights returned by provider
                </div>
              </div>
            </div>
          )}

          {/* Hotel */}
          <div className="flex items-center gap-2 p-2.5 rounded-xl bg-gray-50 dark:bg-gray-800/60 border border-gray-100 dark:border-gray-700/60">
            <div className="p-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400 shrink-0">
              <MapPin className="w-3.5 h-3.5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-gray-900 dark:text-gray-100 truncate">
                {hotel ? hotel.name : 'Hotel unavailable'}
              </div>
              <div className="text-[11px] text-gray-500 dark:text-gray-400 flex items-center gap-2 mt-0.5">
                {hotel?.rating && (
                  <span className="flex items-center text-amber-500 font-medium">
                    <Star className="w-3 h-3 fill-amber-400 mr-0.5" /> {hotel.rating}
                  </span>
                )}
                {hotel?.hotel_class && <span>• {hotel.hotel_class}★</span>}
                {hotel?.nightly_rate?.amount && (
                  <span className="font-medium text-gray-700 dark:text-gray-300">• {formatCurrency(hotel.nightly_rate.amount.amount, hotel.nightly_rate.amount.currency)}/nt</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Warnings */}
        {pkg.warnings && pkg.warnings.length > 0 && (
          <div className="mt-3 p-2 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 flex items-start gap-1.5 text-[11px] text-amber-800 dark:text-amber-300">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
            <span className="truncate">{pkg.warnings[0]}</span>
          </div>
        )}
      </div>

      {/* Action Footer */}
      <div className="p-6 pt-3 border-t border-gray-100 dark:border-gray-800/80 bg-gray-50/50 dark:bg-gray-800/30">
        <button
          onClick={() => onSelect(pkg.package_id)}
          className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 text-white font-bold text-sm shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 group-hover:gap-3"
        >
          <span>Inspect & Customize Package</span>
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </div>
  );
};
