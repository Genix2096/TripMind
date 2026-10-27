import React, { useState } from 'react';
import type { TravelPackage, FlightOption, HotelOption, SeasonalWeatherEstimate } from '../types';
import { BudgetBreakdown } from './BudgetBreakdown';
import {
  ArrowLeft,
  Plane,
  MapPin,
  Calendar,
  CloudSun,
  Navigation,
  CheckCircle,
  AlertTriangle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Star,
  Info,
  Layers,
  Sparkles,
  Check,
} from 'lucide-react';

interface PackageDetailsProps {
  pkg: TravelPackage;
  allPackages: TravelPackage[];
  onBack: () => void;
  onSwitchPackage: (pkgId: string) => void;
  onSelectOutboundFlight: (pkgId: string, flight: FlightOption) => void;
  onSelectReturnFlight: (pkgId: string, flight: FlightOption) => void;
  onSelectHotel: (pkgId: string, hotel: HotelOption) => void;
  onSaveTrip: () => void;
  isUpdating?: boolean;
  selectionError?: string | null;
  selectionDisabledReason?: string | null;
  seasonalWeather?: SeasonalWeatherEstimate | null;
}

const formatCurrency = (amount: number | string | undefined | null, curr: string) => {
  if (amount === undefined || amount === null) return '—';
  const num = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(num)) return '—';
  const sym = curr === 'INR' ? '₹' : curr === 'USD' ? '$' : curr === 'EUR' ? '€' : `${curr} `;
  return `${sym}${num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
};

export const PackageDetails: React.FC<PackageDetailsProps> = ({
  pkg,
  allPackages,
  onBack,
  onSwitchPackage,
  onSelectOutboundFlight,
  onSelectReturnFlight,
  onSelectHotel,
  onSaveTrip,
  isUpdating = false,
  selectionError = null,
  selectionDisabledReason = null,
  seasonalWeather = null,
}) => {
  const selectionLocked = isUpdating || !!selectionDisabledReason;
  const [showOutboundAlts, setShowOutboundAlts] = useState(false);
  const [showReturnAlts, setShowReturnAlts] = useState(false);
  const [showHotelAlts, setShowHotelAlts] = useState(false);

  const isWithinBudget = pkg.budget_classification === 'within_budget';
  const isOverBudget = pkg.budget_classification === 'over_budget';
  const isIncomplete = pkg.budget_classification === 'incomplete';

  const outFlight = pkg.selected_outbound_flight;
  const retFlight = pkg.selected_return_flight;
  const hotel = pkg.selected_hotel;

  return (
    <div className="space-y-8 animate-in fade-in duration-300 pb-16">
      {/* Navigation & Package Switcher Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-gray-700 dark:text-gray-300 bg-gray-100 hover:bg-gray-200 dark:bg-gray-750 dark:hover:bg-gray-700 transition-colors w-fit"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Comparison (All 4 Packages)
        </button>

        {/* Quick Package Switcher Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider shrink-0 mr-1 flex items-center gap-1">
            <Layers className="w-3.5 h-3.5" /> Packages:
          </span>
          {allPackages.map((p) => {
            const active = p.package_id === pkg.package_id;
            return (
              <button
                key={p.package_id}
                onClick={() => onSwitchPackage(p.package_id)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap flex items-center gap-1.5 ${
                  active
                    ? 'bg-purple-600 text-white shadow-md'
                    : 'bg-gray-100 dark:bg-gray-700/60 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}
              >
                <span>{p.name.split(':')[0]}</span>
                {p.budget_classification === 'within_budget' && <CheckCircle className="w-3 h-3 text-emerald-400" />}
                {p.budget_classification === 'over_budget' && <AlertTriangle className="w-3 h-3 text-rose-400" />}
              </button>
            );
          })}
        </div>
      </div>

      {/* Package Header Banner */}
      <div className="p-8 rounded-3xl bg-gradient-to-r from-purple-900/10 via-indigo-900/10 to-blue-900/10 dark:from-purple-950/40 dark:via-indigo-950/40 dark:to-blue-950/40 border border-purple-200 dark:border-purple-800/50 shadow-lg">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              {pkg.is_complete ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold tracking-wide uppercase bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  Complete Package
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold tracking-wide uppercase bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                  Partial Package
                </span>
              )}

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

              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 bg-white/80 dark:bg-gray-800/80 px-2.5 py-1 rounded-full border border-gray-200 dark:border-gray-700">
                {pkg.day_wise.length} Days Itinerary
              </span>

              {pkg.trip_pace && (
                <span
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${
                    pkg.trip_pace === 'RUSHED'
                      ? 'bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300 dark:border-amber-800'
                      : pkg.trip_pace === 'SLOW'
                      ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
                      : 'bg-blue-100 text-blue-900 dark:bg-blue-950/60 dark:text-blue-300 border-blue-300 dark:border-blue-800'
                  }`}
                  title={pkg.pace_description || `${pkg.trip_pace} pace`}
                >
                  <span>{pkg.trip_pace === 'RUSHED' ? '⚡' : pkg.trip_pace === 'SLOW' ? '🌿' : '⚖️'}</span>
                  <span>{pkg.trip_pace === 'RUSHED' ? 'Rushed' : pkg.trip_pace === 'SLOW' ? 'Slow' : 'Balanced'} Pace</span>
                </span>
              )}

              {pkg.description.includes('Focus:') && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300 border border-purple-300 dark:border-purple-800">
                  <Sparkles className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />
                  Focus: {pkg.description.split('Focus:')[1].trim()}
                </span>
              )}
            </div>

            <h2 className="text-3xl font-extrabold text-gray-900 dark:text-white leading-tight">
              {pkg.name}
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-300 mt-2 max-w-2xl leading-relaxed">
              {pkg.description}
            </p>
            {pkg.pace_description && (
              <div className="mt-2.5 inline-flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300 bg-white/70 dark:bg-gray-800/70 px-3 py-1.5 rounded-xl border border-gray-200/80 dark:border-gray-700/80">
                <span className="font-bold text-gray-800 dark:text-gray-200">Daily Density:</span>
                <span>{pkg.pace_description}</span>
              </div>
            )}
          </div>

          <div className="flex flex-col sm:flex-row lg:flex-col items-start lg:items-end gap-3 shrink-0">
            <div className="p-4 rounded-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm min-w-[200px]">
              <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider block">
                Calculated Total
              </span>
              <span className="text-2xl font-black text-gray-900 dark:text-white mt-1 block">
                {pkg.total_cost ? formatCurrency(pkg.total_cost.amount, pkg.currency) : 'Price incomplete'}
              </span>
              {!pkg.total_cost && pkg.known_subtotal && (
                <span className="text-xs text-amber-600 dark:text-amber-400 mt-1 block">
                  Known so far: {formatCurrency(pkg.known_subtotal.amount, pkg.known_subtotal.currency || pkg.currency)} (incomplete)
                </span>
              )}
              {isWithinBudget && pkg.remaining_budget && Number(pkg.remaining_budget.amount) > 0 && (
                <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 mt-1 block">
                  {formatCurrency(pkg.remaining_budget.amount, pkg.currency)} under budget
                </span>
              )}
              {isOverBudget && pkg.amount_over_budget && Number(pkg.amount_over_budget.amount) > 0 && (
                <span className="text-xs font-semibold text-rose-600 dark:text-rose-400 mt-1 block">
                  +{formatCurrency(pkg.amount_over_budget.amount, pkg.currency)} over budget
                </span>
              )}
            </div>

            <button
              onClick={onSaveTrip}
              className="px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs shadow-md transition-colors w-full text-center"
            >
              Save This Package Locally
            </button>
          </div>
        </div>
      </div>

      {/* Warnings & Notes */}
      {pkg.warnings && pkg.warnings.length > 0 && (
        <div className="p-4 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 shadow-sm">
          <h4 className="text-sm font-bold text-amber-800 dark:text-amber-300 flex items-center gap-2 mb-2">
            <Info className="w-4 h-4 text-amber-600" /> Package Advisory & Warnings
          </h4>
          <ul className="list-disc pl-5 text-xs text-amber-700 dark:text-amber-400 space-y-1">
            {pkg.warnings.map((w, idx) => (
              <li key={idx}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {selectionDisabledReason && (
        <div role="alert" className="p-4 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300">
          {selectionDisabledReason}
        </div>
      )}
      {selectionError && (
        <div role="alert" className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300">
          {selectionError}
        </div>
      )}
      {isUpdating && (
        <div className="text-xs font-semibold text-purple-600 dark:text-purple-400">Updating…</div>
      )}

      {/* Selected Components & Interactive Alternatives */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-600" />
            Travel Components & Available Alternatives
          </h3>
          <span className="text-xs text-gray-500 dark:text-gray-400">
            Click alternatives below to swap options with immediate budget recalculation
          </span>
        </div>

        {/* 1. Outbound Flight Box */}
        <div className="rounded-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 overflow-hidden shadow-sm">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400">
                  <Plane className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Selected Outbound Flight
                  </div>
                  <div className="text-base font-bold text-gray-900 dark:text-gray-100">
                    {outFlight?.segments[0]?.airline || 'Flight'}{' '}
                    {outFlight?.segments[0]?.flight_number}
                  </div>
                </div>
              </div>

              <div className="text-right">
                <div className="text-base font-extrabold text-gray-900 dark:text-gray-100">
                  {outFlight?.price ? formatCurrency(outFlight.price.amount, outFlight.price.currency) : 'Price unknown'}
                </div>
                <div className="text-xs text-gray-500">
                  {!outFlight ? '' : outFlight.stops === 0 ? 'Nonstop' : `${outFlight.stops} stop(s)`}
                </div>
              </div>
            </div>

            {outFlight ? (
              <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-750/50 border border-gray-100 dark:border-gray-700 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-gray-500 block">Departure</span>
                  <span className="font-bold text-gray-900 dark:text-gray-100 text-sm">
                    {outFlight.segments[0]?.departure?.code ?? '?'}
                  </span>
                  <span className="text-gray-600 dark:text-gray-300 block">
                    {outFlight.segments[0]?.departure?.local_time ? new Date(outFlight.segments[0].departure.local_time).toLocaleString() : 'Time not specified'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 block">Arrival</span>
                  <span className="font-bold text-gray-900 dark:text-gray-100 text-sm">
                    {outFlight.segments[outFlight.segments.length - 1]?.arrival?.code ?? '?'}
                  </span>
                  <span className="text-gray-600 dark:text-gray-300 block">
                    {(() => {
                      const t = outFlight.segments[outFlight.segments.length - 1]?.arrival?.local_time;
                      return t ? new Date(t).toLocaleString() : 'Time not specified';
                    })()}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 block">Duration & Aircraft</span>
                  <span className="font-semibold text-gray-900 dark:text-gray-100">
                    {outFlight.total_duration_minutes ? `${Math.floor(outFlight.total_duration_minutes / 60)}h ${outFlight.total_duration_minutes % 60}m` : '—'}
                  </span>
                  <span className="text-gray-500 block">
                    {outFlight.segments[0]?.aircraft || 'Standard aircraft'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-800 text-xs text-gray-500 italic">
                No outbound flight selected or returned by provider.
              </div>
            )}

            {/* Outbound Alternatives Toggle */}
            {pkg.outbound_flight_alternatives.length > 0 && (
              <button
                onClick={() => setShowOutboundAlts(!showOutboundAlts)}
                className="mt-4 flex items-center gap-1.5 text-xs font-semibold text-purple-600 dark:text-purple-400 hover:text-purple-700 dark:hover:text-purple-300 transition-colors"
              >
                <span>
                  {showOutboundAlts ? 'Hide' : 'View'} Outbound Alternatives ({pkg.outbound_flight_alternatives.length} available)
                </span>
                {showOutboundAlts ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>

          {/* Outbound Alternatives List */}
          {showOutboundAlts && pkg.outbound_flight_alternatives.length > 0 && (
            <div className="p-6 pt-0 border-t border-gray-100 dark:border-gray-700/60 bg-gray-50/50 dark:bg-gray-800/40 space-y-3">
              <h5 className="text-xs font-bold text-gray-500 uppercase tracking-wider pt-4">
                Available Alternative Outbound Flights
              </h5>
              <div className="grid gap-3">
                {pkg.outbound_flight_alternatives.map((alt) => (
                  <div
                    key={alt.option_id}
                    className="p-4 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div>
                      <div className="font-bold text-sm text-gray-900 dark:text-gray-100">
                        {alt.segments[0]?.airline || 'Flight'} {alt.segments[0]?.flight_number}
                      </div>
                      <div className="text-xs text-gray-500 mt-1 flex items-center gap-2">
                        <span>{alt.segments[0]?.departure?.code ?? '?'} → {alt.segments[alt.segments.length - 1]?.arrival?.code ?? '?'}</span>
                        <span>• {alt.stops === 0 ? 'Nonstop' : `${alt.stops} stop`}</span>
                        {alt.total_duration_minutes && <span>• {Math.floor(alt.total_duration_minutes / 60)}h {alt.total_duration_minutes % 60}m</span>}
                      </div>
                    </div>

                    <div className="flex items-center gap-4 self-end sm:self-auto">
                      <div className="text-right">
                        <div className="font-extrabold text-sm text-gray-900 dark:text-gray-100">
                          {alt.price ? formatCurrency(alt.price.amount, alt.price.currency) : 'Price unknown'}
                        </div>
                      </div>
                      <button
                        onClick={() => onSelectOutboundFlight(pkg.package_id, alt)}
                        disabled={selectionLocked}
                        className="px-3 py-1.5 rounded-lg bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 hover:bg-purple-200 dark:hover:bg-purple-800/60 text-xs font-bold transition-colors flex items-center gap-1"
                      >
                        <Check className="w-3.5 h-3.5" /> Select Option
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 2. Return Flight Box */}
        <div className="rounded-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 overflow-hidden shadow-sm">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-xl ${retFlight ? 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400' : 'bg-gray-100 dark:bg-gray-750 text-gray-400'}`}>
                  <Plane className="w-5 h-5 rotate-180" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Selected Return Flight
                  </div>
                  <div className="text-base font-bold text-gray-900 dark:text-gray-100">
                    {retFlight ? `${retFlight.segments[0]?.airline || 'Flight'} ${retFlight.segments[0]?.flight_number}` : 'Return Flight Unavailable'}
                  </div>
                </div>
              </div>

              {retFlight && (
                <div className="text-right">
                  <div className="text-base font-extrabold text-gray-900 dark:text-gray-100">
                    {retFlight.price ? formatCurrency(retFlight.price.amount, retFlight.price.currency) : 'Price unknown'}
                  </div>
                  <div className="text-xs text-gray-500">
                    {retFlight.stops === 0 ? 'Nonstop' : `${retFlight.stops} stop(s)`}
                  </div>
                </div>
              )}
            </div>

            {retFlight ? (
              <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-750/50 border border-gray-100 dark:border-gray-700 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div>
                  <span className="text-gray-500 block">Departure</span>
                  <span className="font-bold text-gray-900 dark:text-gray-100 text-sm">
                    {retFlight.segments[0]?.departure?.code ?? '?'}
                  </span>
                  <span className="text-gray-600 dark:text-gray-300 block">
                    {retFlight.segments[0]?.departure?.local_time ? new Date(retFlight.segments[0].departure.local_time).toLocaleString() : 'Time not specified'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 block">Arrival</span>
                  <span className="font-bold text-gray-900 dark:text-gray-100 text-sm">
                    {retFlight.segments[retFlight.segments.length - 1]?.arrival?.code ?? '?'}
                  </span>
                  <span className="text-gray-600 dark:text-gray-300 block">
                    {(() => {
                      const t = retFlight.segments[retFlight.segments.length - 1]?.arrival?.local_time;
                      return t ? new Date(t).toLocaleString() : 'Time not specified';
                    })()}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500 block">Duration & Aircraft</span>
                  <span className="font-semibold text-gray-900 dark:text-gray-100">
                    {retFlight.total_duration_minutes ? `${Math.floor(retFlight.total_duration_minutes / 60)}h ${retFlight.total_duration_minutes % 60}m` : '—'}
                  </span>
                  <span className="text-gray-500 block">
                    {retFlight.segments[0]?.aircraft || 'Standard aircraft'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-800 text-xs text-gray-500 italic">
                No usable return flights returned by provider.
              </div>
            )}

            {/* Return Alternatives Toggle */}
            {pkg.return_flight_alternatives.length > 0 && (
              <button
                onClick={() => setShowReturnAlts(!showReturnAlts)}
                className="mt-4 flex items-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors"
              >
                <span>
                  {showReturnAlts ? 'Hide' : 'View'} Return Alternatives ({pkg.return_flight_alternatives.length} available)
                </span>
                {showReturnAlts ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>

          {/* Return Alternatives List */}
          {showReturnAlts && pkg.return_flight_alternatives.length > 0 && (
            <div className="p-6 pt-0 border-t border-gray-100 dark:border-gray-700/60 bg-gray-50/50 dark:bg-gray-800/40 space-y-3">
              <h5 className="text-xs font-bold text-gray-500 uppercase tracking-wider pt-4">
                Available Alternative Return Flights
              </h5>
              <div className="grid gap-3">
                {pkg.return_flight_alternatives.map((alt) => (
                  <div
                    key={alt.option_id}
                    className="p-4 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div>
                      <div className="font-bold text-sm text-gray-900 dark:text-gray-100">
                        {alt.segments[0]?.airline || 'Flight'} {alt.segments[0]?.flight_number}
                      </div>
                      <div className="text-xs text-gray-500 mt-1 flex items-center gap-2">
                        <span>{alt.segments[0]?.departure?.code ?? '?'} → {alt.segments[alt.segments.length - 1]?.arrival?.code ?? '?'}</span>
                        <span>• {alt.stops === 0 ? 'Nonstop' : `${alt.stops} stop`}</span>
                        {alt.total_duration_minutes && <span>• {Math.floor(alt.total_duration_minutes / 60)}h {alt.total_duration_minutes % 60}m</span>}
                      </div>
                    </div>

                    <div className="flex items-center gap-4 self-end sm:self-auto">
                      <div className="text-right">
                        <div className="font-extrabold text-sm text-gray-900 dark:text-gray-100">
                          {alt.price ? formatCurrency(alt.price.amount, alt.price.currency) : 'Price unknown'}
                        </div>
                      </div>
                      <button
                        onClick={() => onSelectReturnFlight(pkg.package_id, alt)}
                        disabled={selectionLocked}
                        className="px-3 py-1.5 rounded-lg bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300 hover:bg-indigo-200 dark:hover:bg-indigo-800/60 text-xs font-bold transition-colors flex items-center gap-1"
                      >
                        <Check className="w-3.5 h-3.5" /> Select Option
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 3. Hotel Box */}
        <div className="rounded-2xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 overflow-hidden shadow-sm">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400">
                  <MapPin className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Selected Accommodation
                  </div>
                  <div className="text-base font-bold text-gray-900 dark:text-gray-100">
                    {hotel?.name || 'Hotel unavailable'}
                  </div>
                </div>
              </div>

              <div className="text-right">
                <div className="text-base font-extrabold text-gray-900 dark:text-gray-100">
                  {hotel?.total_rate?.amount ? (
                    formatCurrency(hotel.total_rate.amount.amount, hotel.total_rate.amount.currency)
                  ) : hotel?.nightly_rate?.amount ? (
                    `${formatCurrency(hotel.nightly_rate.amount.amount, hotel.nightly_rate.amount.currency)} / nt`
                  ) : hotel?.nightly_rate?.display_text || 'Price unknown'}
                </div>
                <div className="text-xs text-gray-500 flex items-center justify-end gap-1">
                  {hotel?.rating && (
                    <span className="flex items-center text-amber-500 font-semibold">
                      <Star className="w-3 h-3 fill-amber-400 mr-0.5" /> {hotel.rating}
                    </span>
                  )}
                  {hotel?.hotel_class && <span>• {hotel.hotel_class} Star Class</span>}
                </div>
              </div>
            </div>

            {hotel ? (
              <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-750/50 border border-gray-100 dark:border-gray-700 space-y-2 text-xs">
                {hotel.address && (
                  <div className="text-gray-600 dark:text-gray-300">
                    <strong>Address:</strong> {hotel.address}
                  </div>
                )}
                {hotel.description && (
                  <div className="text-gray-600 dark:text-gray-300 line-clamp-2">
                    {hotel.description}
                  </div>
                )}
                {hotel.amenities && hotel.amenities.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {hotel.amenities.slice(0, 6).map((a, i) => (
                      <span key={i} className="px-2 py-0.5 rounded-md bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-[11px] text-gray-700 dark:text-gray-300">
                        {a}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-800 text-xs text-gray-500 italic">
                No hotel selected or returned by provider.
              </div>
            )}

            {/* Hotel Alternatives Toggle */}
            {pkg.hotel_alternatives.length > 0 && (
              <button
                onClick={() => setShowHotelAlts(!showHotelAlts)}
                className="mt-4 flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 transition-colors"
              >
                <span>
                  {showHotelAlts ? 'Hide' : 'View'} Hotel Alternatives ({pkg.hotel_alternatives.length} available)
                </span>
                {showHotelAlts ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>

          {/* Hotel Alternatives List */}
          {showHotelAlts && pkg.hotel_alternatives.length > 0 && (
            <div className="p-6 pt-0 border-t border-gray-100 dark:border-gray-700/60 bg-gray-50/50 dark:bg-gray-800/40 space-y-3">
              <h5 className="text-xs font-bold text-gray-500 uppercase tracking-wider pt-4">
                Available Alternative Accommodations
              </h5>
              <div className="grid gap-3">
                {pkg.hotel_alternatives.map((alt) => (
                  <div
                    key={alt.hotel_id}
                    className="p-4 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                  >
                    <div>
                      <div className="font-bold text-sm text-gray-900 dark:text-gray-100 flex items-center gap-2">
                        <span>{alt.name}</span>
                        {alt.rating && (
                          <span className="flex items-center text-xs text-amber-500 font-semibold">
                            <Star className="w-3 h-3 fill-amber-400 mr-0.5" /> {alt.rating}
                          </span>
                        )}
                        {alt.hotel_class && <span className="text-xs text-gray-400">• {alt.hotel_class}★</span>}
                      </div>
                      <div className="text-xs text-gray-500 mt-1 line-clamp-1">
                        {alt.description || alt.address || 'Verified hotel property'}
                      </div>
                    </div>

                    <div className="flex items-center gap-4 self-end sm:self-auto">
                      <div className="text-right">
                        <div className="font-extrabold text-sm text-gray-900 dark:text-gray-100">
                          {alt.total_rate?.amount ? (
                            formatCurrency(alt.total_rate.amount.amount, alt.total_rate.amount.currency)
                          ) : alt.nightly_rate?.amount ? (
                            `${formatCurrency(alt.nightly_rate.amount.amount, alt.nightly_rate.amount.currency)} / nt`
                          ) : alt.nightly_rate?.display_text || 'Price unknown'}
                        </div>
                      </div>
                      <button
                        onClick={() => onSelectHotel(pkg.package_id, alt)}
                        disabled={selectionLocked}
                        className="px-3 py-1.5 rounded-lg bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 hover:bg-emerald-200 dark:hover:bg-emerald-800/60 text-xs font-bold transition-colors flex items-center gap-1"
                      >
                        <Check className="w-3.5 h-3.5" /> Select Option
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Independent Budget Report */}
      <BudgetBreakdown
        report={pkg.budget_report}
        totalCost={pkg.total_cost}
        remainingBudget={pkg.remaining_budget}
        amountOverBudget={pkg.amount_over_budget}
        currency={pkg.currency}
      />

      {/* Weather & Seasonal Climate Section */}
      {seasonalWeather && (
        <div className="p-6 rounded-3xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-xl space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-sky-100 dark:bg-sky-900/40 text-sky-600 dark:text-sky-400">
                <CloudSun className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-gray-900 dark:text-gray-100">
                  Weather & Climate Context
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {seasonalWeather.destination}
                  {seasonalWeather.travel_month ? ` • ${seasonalWeather.travel_month}` : ''}
                  {seasonalWeather.season_name ? ` (${seasonalWeather.season_name})` : ''}
                </p>
              </div>
            </div>

            {seasonalWeather.status === 'forecast_available' ? (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 flex items-center gap-1.5">
                <CheckCircle className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                Date-Specific Forecast Available
              </span>
            ) : seasonalWeather.status === 'forecast_unavailable_seasonal_available' ? (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-sky-100 text-sky-800 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-300 dark:border-sky-800 flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-sky-600 dark:text-sky-400" />
                Historical Seasonal Estimate
              </span>
            ) : (
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800 flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                Forecast & Seasonal Data Unavailable
              </span>
            )}
          </div>

          {seasonalWeather.status === 'forecast_unavailable_seasonal_available' && (
            <div className="p-4 rounded-xl bg-sky-50/60 dark:bg-sky-950/20 border border-sky-100 dark:border-sky-900/40 text-xs space-y-2">
              <div className="font-semibold text-sky-900 dark:text-sky-200">
                {seasonalWeather.disclaimer || 'Typical weather for this time of year (historical estimate, not a date-specific prediction)'}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-gray-700 dark:text-gray-300">
                {seasonalWeather.typical_temp_min_c !== undefined && seasonalWeather.typical_temp_max_c !== undefined && (
                  <div><strong>Historical Temperatures:</strong> {seasonalWeather.typical_temp_min_c}°C – {seasonalWeather.typical_temp_max_c}°C</div>
                )}
                {seasonalWeather.precipitation_context && (
                  <div className="sm:col-span-2"><strong>Rainfall Context:</strong> {seasonalWeather.precipitation_context}</div>
                )}
              </div>
              {seasonalWeather.seasonal_caveats && seasonalWeather.seasonal_caveats.length > 0 && (
                <div className="pt-1 text-amber-700 dark:text-amber-300">
                  <strong>Caveats:</strong> {seasonalWeather.seasonal_caveats.join(' • ')}
                </div>
              )}
              {(seasonalWeather.data_source || seasonalWeather.reference_period) && (
                <div className="text-[11px] text-gray-500 dark:text-gray-400 pt-1 border-t border-sky-100 dark:border-sky-900/40">
                  Source: {seasonalWeather.data_source || 'Historical records'}{seasonalWeather.reference_period ? ` (${seasonalWeather.reference_period})` : ''}
                </div>
              )}
            </div>
          )}

          {seasonalWeather.status === 'forecast_and_seasonal_unavailable' && (
            <div className="p-4 rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/40 text-xs text-amber-800 dark:text-amber-200 space-y-1.5">
              <div className="font-bold">Forecast Horizon Exceeded & Climatology Unavailable</div>
              {seasonalWeather.notes && seasonalWeather.notes.length > 0 && (
                <ul className="list-disc list-inside space-y-1">
                  {seasonalWeather.notes.map((note, nIdx) => (
                    <li key={nIdx}>{note}</li>
                  ))}
                </ul>
              )}
              {seasonalWeather.disclaimer && (
                <div className="text-[11px] text-amber-700 dark:text-amber-300 pt-1">
                  <em>{seasonalWeather.disclaimer}</em>
                </div>
              )}
            </div>
          )}

          {seasonalWeather.status === 'forecast_available' && seasonalWeather.notes && (
            <div className="p-3 rounded-xl bg-emerald-50/50 dark:bg-emerald-950/20 text-xs text-emerald-800 dark:text-emerald-200">
              {seasonalWeather.notes.join(' • ')}
            </div>
          )}
        </div>
      )}

      {/* Day-by-Day Tailored Itinerary */}
      <div className="p-8 rounded-3xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-xl space-y-6">
        <div className="border-b border-gray-200 dark:border-gray-700 pb-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <Calendar className="w-6 h-6 text-purple-600" />
                Complete Day-by-Day Itinerary
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Tailored specifically around this package's flight timings, hotel check-in/out, and attraction focus
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap self-start sm:self-auto">
              {pkg.trip_pace && (
                <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border shadow-sm ${
                  pkg.trip_pace === 'RUSHED'
                    ? 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                    : pkg.trip_pace === 'SLOW'
                    ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                    : 'bg-blue-50 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800'
                }`}>
                  <span>{pkg.trip_pace === 'RUSHED' ? '⚡' : pkg.trip_pace === 'SLOW' ? '🌿' : '⚖️'}</span>
                  <span>{pkg.trip_pace === 'RUSHED' ? 'Rushed' : pkg.trip_pace === 'SLOW' ? 'Slow' : 'Balanced'} Density</span>
                </span>
              )}
              {pkg.description.includes('Focus:') && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold bg-purple-50 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800 shadow-sm">
                  <Sparkles className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400 shrink-0" />
                  Focus: {pkg.description.split('Focus:')[1].trim()}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          {pkg.day_wise.map((day, idx) => (
            <div key={idx} className="bg-gray-50 dark:bg-gray-750/50 p-6 rounded-2xl border border-gray-200/60 dark:border-gray-700/60">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-lg font-bold text-gray-900 dark:text-gray-100">
                  Day {idx + 1}: {day.title}
                </h4>
                {day.date && (
                  <span className="text-xs font-medium text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-700 px-2.5 py-1 rounded-md border border-gray-200 dark:border-gray-600">
                    {new Date(day.date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
                  </span>
                )}
              </div>

              {day.weather_summary && (
                <div className="text-xs text-blue-600 dark:text-blue-400 mb-4 flex items-center gap-1.5 font-medium">
                  <CloudSun className="w-4 h-4 shrink-0" />
                  <span>{day.weather_summary}</span>
                </div>
              )}

              <ul className="space-y-3 mt-3">
                {day.activities.map((act, aIdx) => (
                  <li
                    key={aIdx}
                    className="p-4 rounded-xl bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 shadow-sm flex items-start gap-3"
                  >
                    <span className="mt-1.5 w-2.5 h-2.5 rounded-full bg-purple-500 shrink-0"></span>
                    <div className="flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <h5 className="font-bold text-sm text-gray-900 dark:text-gray-100">
                          {act.name}
                        </h5>
                        {act.time_window && (
                          <span className="text-xs font-medium text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-950/40 px-2 py-0.5 rounded">
                            {act.time_window}
                          </span>
                        )}
                      </div>
                      {act.description && (
                        <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 leading-relaxed">
                          {act.description}
                        </p>
                      )}
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
                        {act.location && (
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3.5 h-3.5" /> {act.location}
                          </span>
                        )}
                        {act.travel_info && (
                          <span className="flex items-center gap-1">
                            <Navigation className="w-3.5 h-3.5" /> {act.travel_info}
                          </span>
                        )}
                        {act.data_source && (
                          <span className="text-[10px] text-gray-400">
                            via {act.data_source}
                          </span>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>

              {day.missing_information && day.missing_information.length > 0 && (
                <div className="mt-4 p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300">
                  <strong>Notice:</strong> {day.missing_information.join(', ')}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
