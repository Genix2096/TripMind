import React from 'react';
import { AlertTriangle, Info, Plane, MapPin, RotateCcw } from 'lucide-react';
import type { StructuredItinerary } from '../types';

interface LegacyItineraryProps {
  itinerary: StructuredItinerary;
  notes: string[];
  isLegacy: boolean;
  onReset: () => void;
}

const money = (m?: { amount: number | string; currency: string } | null) =>
  m ? `${m.currency} ${m.amount}` : 'Price not provided';

/**
 * Shown when an itinerary exists but there are no comparable packages (older saved trip, zero packages
 * generated, or provider failures). It only displays what the providers actually returned; it never
 * builds or implies a package.
 */
export const LegacyItinerary: React.FC<LegacyItineraryProps> = ({ itinerary, notes, isLegacy, onReset }) => {
  const problems = Object.values(itinerary.provider_statuses ?? {}).filter(
    (s) => s && ['error', 'unavailable', 'empty'].includes(s.status)
  );
  const flights = Array.isArray(itinerary.flights) ? itinerary.flights : [];
  const hotels = Array.isArray(itinerary.hotels) ? itinerary.hotels : [];
  const days = Array.isArray(itinerary.day_wise) ? itinerary.day_wise : [];

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      <div className="p-5 rounded-2xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 flex items-start gap-3" role="status">
        <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="text-sm text-amber-900 dark:text-amber-200 space-y-1">
          <div className="font-bold">
            {isLegacy
              ? 'This trip was saved before travel packages existed.'
              : 'No comparable travel packages could be built for this trip.'}
          </div>
          <div className="text-xs">
            {isLegacy
              ? 'Your original itinerary and provider results are shown below. Plan the trip again to get selectable packages.'
              : 'The provider results did not support a complete package. What was returned is shown below; nothing has been filled in.'}
          </div>
          {notes.map((n, i) => (
            <div key={i} className="text-xs">• {n}</div>
          ))}
        </div>
      </div>

      {problems.length > 0 && (
        <div className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-200 space-y-1">
          <div className="font-bold flex items-center gap-1.5"><Info className="w-4 h-4" /> Partial results</div>
          {problems.map((s, i) => (
            <div key={i}>{s?.capability || 'Search'}: {s?.status}{s?.error_detail ? ` — ${s.error_detail}` : ''}</div>
          ))}
        </div>
      )}

      <div className="p-6 rounded-3xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm space-y-4">
        <h2 className="text-2xl font-black text-gray-900 dark:text-white">Itinerary</h2>
        <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{itinerary.trip_summary}</p>
        {(itinerary.validation_warnings ?? []).length > 0 && (
          <ul className="list-disc pl-5 text-xs text-orange-700 dark:text-orange-400 space-y-1">
            {(itinerary.validation_warnings ?? []).map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        )}
        {days.map((day, i) => (
          <div key={i} className="p-4 rounded-2xl bg-gray-50 dark:bg-gray-900/40 border border-gray-100 dark:border-gray-700">
            <div className="font-bold text-sm text-gray-900 dark:text-gray-100">
              Day {i + 1}: {day.title}
              {day.date && <span className="ml-2 text-xs font-normal text-gray-500">{new Date(day.date).toLocaleDateString()}</span>}
            </div>
            <ul className="mt-2 space-y-1 text-xs text-gray-700 dark:text-gray-300">
              {(day.activities ?? []).map((a, j) => (
                <li key={j}>• <span className="font-semibold">{a.name}</span>{a.description ? ` — ${a.description}` : ''}</li>
              ))}
            </ul>
            {(day.missing_information ?? []).length > 0 && (
              <div className="mt-2 text-xs text-amber-700 dark:text-amber-400">{(day.missing_information ?? []).join(', ')}</div>
            )}
          </div>
        ))}
      </div>

      {flights.length > 0 && (
        <div className="p-6 rounded-3xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 space-y-3">
          <h3 className="text-sm font-bold uppercase tracking-wider text-gray-500 flex items-center gap-2"><Plane className="w-4 h-4" /> Flight results returned by the provider</h3>
          <div className="grid gap-3 md:grid-cols-2">
            {flights.map((f, i) => {
              const first = f.segments?.[0];
              const last = f.segments?.[f.segments.length - 1];
              return (
                <div key={`${f.option_id}-${i}`} className="p-3 rounded-xl border border-gray-200 dark:border-gray-700 text-xs">
                  <div className="font-semibold">{first?.departure?.code ?? '?'} → {last?.arrival?.code ?? '?'}</div>
                  <div className="text-gray-500 mt-1">{money(f.price)} · {first?.airline ?? 'Airline not provided'}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {hotels.length > 0 && (
        <div className="p-6 rounded-3xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 space-y-3">
          <h3 className="text-sm font-bold uppercase tracking-wider text-gray-500 flex items-center gap-2"><MapPin className="w-4 h-4" /> Hotel results returned by the provider</h3>
          <div className="grid gap-3 md:grid-cols-2">
            {hotels.map((h, i) => (
              <div key={`${h.hotel_id}-${i}`} className="p-3 rounded-xl border border-gray-200 dark:border-gray-700 text-xs">
                <div className="font-semibold">{h.name ?? 'Unnamed property'}</div>
                <div className="text-gray-500 mt-1">
                  {h.total_rate?.amount ? `${money(h.total_rate.amount)} total` : h.nightly_rate?.amount ? `${money(h.nightly_rate.amount)} / night` : h.nightly_rate?.display_text ?? 'Price not provided'}
                  {h.rating ? ` · rating ${h.rating}` : ''}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={onReset}
        className="px-6 py-3 rounded-xl bg-purple-600 hover:bg-purple-700 text-white font-bold text-sm flex items-center gap-2"
      >
        <RotateCcw className="w-4 h-4" /> Plan a new trip
      </button>
    </div>
  );
};
