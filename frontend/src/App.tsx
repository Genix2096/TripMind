import React, { useEffect, useState } from 'react';
import {
  Plane,
  Sparkles,
  Loader2,
  Info,
  Navigation,
  CloudSun,
  CreditCard,
  CheckCircle,
  History,
  Trash2,
  Compass,
  Layers,
} from 'lucide-react';
import type { TravelPackage, StructuredItinerary } from './types';
import { PackageCard } from './components/PackageCard';
import { PackageDetails } from './components/PackageDetails';
import { LegacyItinerary } from './components/LegacyItinerary';
import {
  buildHistoryEntry,
  clearActiveState,
  isPackage,
  loadActiveState,
  loadHistory,
  normalizeSavedTrip,
  sanitizePackages,
  saveActiveState,
  saveHistory,
} from './storage';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000';

interface TripFormProps {
  onSubmit: (request: string, pace?: 'RUSHED' | 'BALANCED' | 'SLOW') => void;
  isLoading: boolean;
}

const TripForm: React.FC<TripFormProps> = ({ onSubmit, isLoading }) => {
  const [request, setRequest] = useState('');
  const [pace, setPace] = useState<'RUSHED' | 'BALANCED' | 'SLOW'>('BALANCED');

  const samplePrompts = [
    "Plan a 5-day trip to Tokyo next month with a $3,000 budget for 2 adults.",
    "Honeymoon in Paris for 7 days starting next week, budget $4,500, love boutique hotels.",
    "Weekend getaway from New York to Miami for 2 travelers, $1,500 budget.",
  ];

  return (
    <div className="w-full max-w-3xl mx-auto p-8 rounded-3xl bg-white/90 dark:bg-gray-800/90 backdrop-blur-xl shadow-2xl border border-gray-200/80 dark:border-gray-700/80">
      <div className="flex items-center gap-3 mb-2">
        <div className="p-2.5 rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-600 text-white shadow-md">
          <Sparkles className="w-6 h-6" />
        </div>
        <div>
          <h2 className="text-2xl font-black text-gray-900 dark:text-white tracking-tight">
            Dream Your Next Trip
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            TripMind builds up to 4 selectable packages from real flight and hotel results
          </p>
        </div>
      </div>

      <div className="space-y-4 mt-6">
        <div>
          <label className="block text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider mb-2">
            Describe your ideal trip in natural language
          </label>
          <textarea
            rows={4}
            className="w-full px-4 py-3.5 rounded-2xl bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 focus:ring-4 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all resize-none text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400"
            placeholder="e.g., I want to travel from New York to London for 5 days starting next Monday. My budget is $3,500. We prefer direct flights and central hotels."
            value={request}
            onChange={(e) => setRequest(e.target.value)}
          />
        </div>

        {/* Trip Pacing Preference Selector */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-xs font-bold text-gray-700 dark:text-gray-300 uppercase tracking-wider">
              Trip Pacing & Density
            </label>
            <span className="text-[11px] text-gray-500 dark:text-gray-400">
              {pace === 'RUSHED'
                ? 'High density (3–4 sights/day, packed schedule)'
                : pace === 'SLOW'
                ? 'Relaxed pace (1–2 sights/day, 2+ hrs free downtime)'
                : 'Balanced pacing (2–3 sights/day, comfortable breaks)'}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 p-1 bg-gray-100 dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-700">
            <button
              type="button"
              onClick={() => setPace('SLOW')}
              className={`py-2 px-3 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                pace === 'SLOW'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-200/60 dark:hover:bg-gray-800'
              }`}
            >
              <span>🌿</span>
              <span>Slow Pace</span>
            </button>
            <button
              type="button"
              onClick={() => setPace('BALANCED')}
              className={`py-2 px-3 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                pace === 'BALANCED'
                  ? 'bg-purple-600 text-white shadow-md'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-200/60 dark:hover:bg-gray-800'
              }`}
            >
              <span>⚖️</span>
              <span>Balanced</span>
              <span className="text-[10px] opacity-80 font-normal hidden sm:inline">(Default)</span>
            </button>
            <button
              type="button"
              onClick={() => setPace('RUSHED')}
              className={`py-2 px-3 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
                pace === 'RUSHED'
                  ? 'bg-amber-600 text-white shadow-md'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-200/60 dark:hover:bg-gray-800'
              }`}
            >
              <span>⚡</span>
              <span>Rushed Pace</span>
            </button>
          </div>
        </div>

        {/* Attraction Interest Chips (Optional Natural Language Helpers) */}
        <div>
          <span className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 block mb-1.5">
            Add Interests (Optional):
          </span>
          <div className="flex flex-wrap items-center gap-1.5">
            {[
              { label: '🏛️ Heritage & Architecture', text: 'I like historical architecture and heritage sites' },
              { label: '🌿 Wildlife & Nature', text: 'focused on wildlife sanctuaries and nature' },
              { label: '🏖️ Beaches & Coastal', text: 'interested in beaches and coastal relaxation' },
              { label: '🎨 Museums & Art', text: 'love visiting museums and cultural exhibits' },
              { label: '🍜 Food & Markets', text: 'focused on local cuisine, street food and markets' },
              { label: '⛰️ Adventure & Outdoors', text: 'keen on outdoor adventure and scenic hikes' },
            ].map((chip, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setRequest((prev) => {
                    const trimmed = prev.trim();
                    if (!trimmed) {
                      return `Plan a 5-day trip. ${chip.text}.`;
                    }
                    if (trimmed.toLowerCase().includes(chip.text.toLowerCase())) {
                      return trimmed;
                    }
                    const cleanEnd = trimmed.replace(/[.,;]+$/, '');
                    return `${cleanEnd}. ${chip.text}.`;
                  });
                }}
                className="text-[11px] px-2.5 py-1 rounded-lg bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/60 border border-purple-200 dark:border-purple-800 transition-colors"
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>

        {/* Suggestion Chips */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold text-gray-400">Suggestions:</span>
          {samplePrompts.map((prompt, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setRequest(prompt)}
              className="text-[11px] px-2.5 py-1 rounded-lg bg-gray-100 hover:bg-purple-50 dark:bg-gray-750 dark:hover:bg-purple-950/40 text-gray-600 dark:text-gray-300 hover:text-purple-600 dark:hover:text-purple-300 border border-gray-200 dark:border-gray-700 transition-colors"
            >
              {prompt.split(',')[0]}...
            </button>
          ))}
        </div>

        <button
          onClick={() => onSubmit(request, pace)}
          disabled={!request.trim() || isLoading}
          className="w-full py-4 rounded-2xl bg-gradient-to-r from-purple-600 via-indigo-600 to-blue-600 hover:from-purple-700 hover:via-indigo-700 hover:to-blue-700 text-white font-bold text-base shadow-xl hover:shadow-2xl hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Building travel packages...
            </>
          ) : (
            <>
              <Compass className="w-5 h-5" />
              Explore Travel Packages
            </>
          )}
        </button>
      </div>
    </div>
  );
};

interface ProgressEvent {
  stage: string;
  message: string;
  data?: any;
}

const StageIcon = ({ stage }: { stage: string }) => {
  switch (stage) {
    case 'understanding': return <Info className="w-4 h-4" />;
    case 'flight_research': return <Plane className="w-4 h-4" />;
    case 'hotel_research': return <Layers className="w-4 h-4" />;
    case 'attractions': return <Sparkles className="w-4 h-4" />;
    case 'routing': return <Navigation className="w-4 h-4" />;
    case 'weather': return <CloudSun className="w-4 h-4" />;
    case 'budget': return <CreditCard className="w-4 h-4" />;
    case 'synthesis': return <CheckCircle className="w-4 h-4" />;
    default: return <Loader2 className="w-4 h-4 animate-spin" />;
  }
};

const PlanningProgress = ({ events, isComplete }: { events: ProgressEvent[]; isComplete: boolean }) => {
  return (
    <div className="w-full max-w-2xl mx-auto mt-8 space-y-3">
      {events.map((e, idx) => (
        <div
          key={idx}
          className="p-3.5 rounded-2xl bg-white dark:bg-gray-800 shadow-sm border border-gray-100 dark:border-gray-700/80 flex items-center gap-3.5 animate-in slide-in-from-bottom-2 fade-in duration-300"
        >
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded-xl shrink-0">
            <StageIcon stage={e.stage} />
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="font-bold text-xs text-gray-900 dark:text-gray-100 uppercase tracking-wider">
              {e.stage.replace('_', ' ')}
            </h4>
            <p className="text-gray-600 dark:text-gray-300 text-xs mt-0.5 truncate">{e.message}</p>
          </div>
        </div>
      ))}
      {!isComplete && events.length > 0 && (
        <div className="p-4 flex items-center justify-center gap-2 text-gray-500">
          <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
          <span className="text-xs font-semibold">Working...</span>
        </div>
      )}
    </div>
  );
};

export default function App() {
  // Restore the active (possibly customised) results once, validated and versioned.
  const [initial] = useState(() => loadActiveState());

  const [isLoading, setIsLoading] = useState(false);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [isComplete, setIsComplete] = useState(!!initial);

  // Core results state
  const [itinerary, setItinerary] = useState<StructuredItinerary | null>(initial?.itinerary ?? null);
  const [packages, setPackages] = useState<TravelPackage[]>(initial?.packages ?? []);
  const [packageNotes, setPackageNotes] = useState<string[]>(initial?.packageNotes ?? []);
  const [tripState, setTripState] = useState<any>(initial?.tripState ?? null);
  const [sessionId, setSessionId] = useState<string | null>(initial?.sessionId ?? null);
  const [isLegacy, setIsLegacy] = useState(false);

  // Active view: null for comparison screen, or package_id string for details view
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(initial?.selectedPackageId ?? null);

  // Option-change state (all changes are validated and recalculated by the backend)
  const [updatingPackageId, setUpdatingPackageId] = useState<string | null>(null);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const [sessionLost, setSessionLost] = useState(false);
  const [restored, setRestored] = useState(!!initial);

  // Clarification state
  const [tripStateForClarification, setTripStateForClarification] = useState<any>(null);
  const [clarificationQuestion, setClarificationQuestion] = useState<string | null>(null);

  // Local storage history
  const [savedTrips, setSavedTrips] = useState<any[]>(() => loadHistory());

  // Keep the active results (including selections) across refreshes.
  useEffect(() => {
    if (!itinerary && packages.length === 0) return;
    saveActiveState({ sessionId, itinerary, packages, packageNotes, tripState, selectedPackageId });
  }, [itinerary, packages, packageNotes, tripState, sessionId, selectedPackageId]);

  const resetResults = () => {
    clearActiveState();
    setPackages([]);
    setItinerary(null);
    setPackageNotes([]);
    setTripState(null);
    setTripStateForClarification(null);
    setSessionId(null);
    setSelectedPackageId(null);
    setSelectionError(null);
    setSessionLost(false);
    setRestored(false);
    setIsLegacy(false);
    setEvents([]);
    setIsComplete(false);
  };

  const saveTrip = () => {
    if (!itinerary && packages.length === 0) return;
    const updated = [buildHistoryEntry({ sessionId, itinerary, packages, packageNotes, tripState }), ...savedTrips];
    if (saveHistory(updated)) {
      setSavedTrips(updated);
      alert('Trip saved locally!');
    } else {
      alert('Could not save: browser storage is full or unavailable.');
    }
  };

  const loadTrip = (saved: any) => {
    const n = normalizeSavedTrip(saved);
    if (!n.itinerary && n.packages.length === 0) {
      alert('This saved trip is in an unsupported format and could not be loaded.');
      return;
    }
    setItinerary(n.itinerary);
    setPackages(n.packages);
    setPackageNotes(n.packageNotes);
    setTripState(n.tripState);
    setSessionId(n.sessionId);
    setIsLegacy(n.isLegacy);
    setSelectedPackageId(null);
    setSelectionError(null);
    setSessionLost(false);
    setRestored(true);
    setEvents([]);
    setIsComplete(true);
  };

  const handleSubmit = async (
    request: string,
    existingState: any = null,
    requestedPace: 'RUSHED' | 'BALANCED' | 'SLOW' = 'BALANCED'
  ) => {
    setIsLoading(true);
    if (!existingState) {
      setEvents([]);
      setTripState(null);
      setTripStateForClarification(null);
    }
    setIsComplete(false);
    // A new search replaces all stored results so stale selections can never mix with the new trip.
    clearActiveState();
    setItinerary(null);
    setPackages([]);
    setPackageNotes([]);
    setSessionId(null);
    setSelectedPackageId(null);
    setSelectionError(null);
    setSessionLost(false);
    setRestored(false);
    setIsLegacy(false);
    setClarificationQuestion(null);

    try {
      const response = await fetch(`${API_BASE}/api/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request,
          existing_state: existingState ? JSON.stringify(existingState) : null,
          pace: requestedPace,
        }),
      });

      const { session_id } = await response.json();
      const eventSource = new EventSource(`${API_BASE}/api/plan/${session_id}/stream`);

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setEvents((prev) => [...prev, data]);

        if (data.stage === 'understanding' && data.data?.trip_state) {
          setTripState(data.data.trip_state);
        }

        if (data.stage === 'completed' || data.stage === 'error' || data.stage === 'clarification_needed') {
          eventSource.close();
          setIsComplete(true);
          setIsLoading(false);

          if (data.stage === 'completed') {
            const itin: StructuredItinerary = data.data.itinerary;
            setItinerary(itin);
            // Packages are delivered once, inside the itinerary payload.
            setPackages(sanitizePackages(itin?.packages));
            setPackageNotes(Array.isArray(itin?.package_notes) ? itin.package_notes : []);
            setSessionId(typeof data.data.session_id === 'string' ? data.data.session_id : session_id);
          } else if (data.stage === 'clarification_needed') {
            setClarificationQuestion(data.message);
            if (data.data?.trip_state) {
              setTripStateForClarification(data.data.trip_state);
            }
          }
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setIsComplete(true);
        setIsLoading(false);
        setEvents((prev) => [...prev, { stage: 'error', message: 'Connection to server lost.' }]);
      };
    } catch {
      setIsLoading(false);
      setIsComplete(true);
      setEvents((prev) => [...prev, { stage: 'error', message: 'Failed to start planning session.' }]);
    }
  };

  // Change a package's flight/hotel. Only IDs are sent; the backend validates them against the options
  // that belong to that package, recomputes budget + itinerary from trusted data, and returns the package.
  const changeSelection = async (
    pkgId: string,
    patch: { outbound_flight_id?: string; return_flight_id?: string; hotel_id?: string }
  ) => {
    if (!sessionId || sessionLost) {
      setSelectionError('Options can only be changed while the original search session is active. Run the search again.');
      return;
    }
    setUpdatingPackageId(pkgId);
    setSelectionError(null);
    try {
      const res = await fetch(`${API_BASE}/api/plan/package/recalculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, package_id: pkgId, ...patch }),
      });
      if (res.ok) {
        const data = await res.json();
        if (isPackage(data?.package) && data.package.package_id === pkgId) {
          // Replace only the package that changed; the others are untouched.
          setPackages((prev) => prev.map((p) => (p.package_id === pkgId ? data.package : p)));
          setRestored(false);
        } else {
          setSelectionError('The server returned an unexpected response. Your selection was not changed.');
        }
      } else {
        let detail: any = null;
        try {
          detail = (await res.json())?.detail;
        } catch {
          /* non-JSON error body */
        }
        if (detail?.code === 'session_not_found' || detail?.code === 'session_expired') {
          setSessionLost(true);
        }
        setSelectionError(detail?.message || `The option could not be changed (HTTP ${res.status}).`);
      }
    } catch {
      setSelectionError('Could not reach the server. Your selection was not changed.');
    } finally {
      setUpdatingPackageId(null);
    }
  };

  const activePackage = packages.find((p) => p.package_id === selectedPackageId);
  const hasResult = !!itinerary || packages.length > 0;
  const selectionDisabledReason = sessionLost
    ? 'The search session has expired or the server was restarted, so options can no longer be changed. Run the search again.'
    : !sessionId
    ? 'No active search session is available for this trip, so options cannot be changed.'
    : null;
  const providerProblems = Object.values(itinerary?.provider_statuses ?? {}).filter(
    (s) => s && ['error', 'unavailable', 'empty'].includes(s.status)
  );

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 p-4 sm:p-8">
      {/* Top Navbar */}
      <header className="max-w-7xl mx-auto mb-10 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-6 border-b border-gray-200/80 dark:border-gray-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg">
            <Plane className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-purple-600 via-indigo-600 to-blue-500 tracking-tight">
              TripMind
            </h1>
            <p className="text-xs text-gray-500 dark:text-gray-400 font-medium">
              Multi-Package Autonomous Travel Orchestrator
            </p>
          </div>
        </div>

        {/* Saved Trips Selector */}
        {savedTrips.length > 0 && (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm text-xs">
              <History className="w-3.5 h-3.5 text-gray-400" />
              <select
                className="bg-transparent border-none outline-none text-xs font-semibold text-gray-700 dark:text-gray-200"
                onChange={(e) => {
                  if (e.target.value) {
                    const trip = savedTrips.find((t) => t.id === e.target.value);
                    if (trip) loadTrip(trip);
                    e.target.value = '';
                  }
                }}
              >
                <option value="">Load Past Trip ({savedTrips.length})...</option>
                {savedTrips.map((t) => {
                  let dateLabel = 'Past Trip';
                  try {
                    if (t.date) {
                      const d = new Date(t.date);
                      if (!isNaN(d.getTime())) dateLabel = d.toLocaleDateString();
                    }
                  } catch {
                    /* ignore */
                  }
                  const destination = t.tripState?.destination || 'Trip';
                  return (
                    <option key={t.id} value={t.id}>
                      {dateLabel} — {destination}
                    </option>
                  );
                })}
              </select>
            </div>

            <button
              onClick={() => {
                if (confirm('Clear all saved trip collections?')) {
                  setSavedTrips([]);
                  saveHistory([]);
                }
              }}
              className="p-2 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-xl transition-colors"
              title="Clear Saved History"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        )}
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto">
        {/* Form View when no result */}
        {!hasResult && <TripForm onSubmit={(req, pace) => handleSubmit(req, null, pace)} isLoading={isLoading} />}

        {/* Progress & Clarification During Run */}
        {events.length > 0 && !hasResult && (
          <div className="flex flex-col space-y-6">
            <PlanningProgress events={events} isComplete={isComplete} />

            {clarificationQuestion && (
              <div className="w-full max-w-2xl mx-auto p-6 rounded-3xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 shadow-xl">
                <h3 className="text-lg font-bold text-amber-800 dark:text-amber-300 mb-2 flex items-center gap-2">
                  <Info className="w-5 h-5 text-amber-600" /> Clarification Needed
                </h3>
                <p className="text-sm text-gray-700 dark:text-gray-300 mb-4 leading-relaxed">
                  {clarificationQuestion}
                </p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = e.target as HTMLFormElement;
                    const input = form.elements.namedItem('reply') as HTMLInputElement;
                    if (input.value.trim()) {
                      handleSubmit(input.value, tripStateForClarification);
                    }
                  }}
                  className="flex gap-2"
                >
                  <input
                    name="reply"
                    type="text"
                    placeholder="Provide details here..."
                    className="flex-1 px-4 py-3 rounded-xl bg-white dark:bg-gray-800 border border-amber-300 dark:border-amber-700 focus:ring-2 focus:ring-amber-500 outline-none text-sm text-gray-900 dark:text-gray-100"
                    autoFocus
                  />
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="px-6 py-3 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-bold text-sm transition-colors disabled:opacity-50"
                  >
                    Reply
                  </button>
                </form>
              </div>
            )}
          </div>
        )}

        {/* Itinerary exists but there are no valid packages (older saved trip, zero packages, provider failures) */}
        {packages.length === 0 && itinerary && (
          <LegacyItinerary itinerary={itinerary} notes={packageNotes} isLegacy={isLegacy} onReset={resetResults} />
        )}

        {/* RESULTS: Travel Packages */}
        {packages.length > 0 && (
          <div>
            {/* View A: Comparison View */}
            {!(selectedPackageId && activePackage) && (
              <div className="space-y-8 animate-in fade-in duration-300">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-3xl bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {packages.every((p) => p.is_complete) ? (
                        <span className="px-3 py-1 rounded-full text-xs font-black bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800 uppercase tracking-wider">
                          {packages.length} {packages.length === 1 ? 'Package' : 'Packages'} Ready
                        </span>
                      ) : (
                        <span className="px-3 py-1 rounded-full text-xs font-black bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800 uppercase tracking-wider">
                          {packages.some((p) => p.is_complete)
                            ? `${packages.filter((p) => p.is_complete).length} of ${packages.length} Packages Ready`
                            : 'Partial Package Generated (Components Incomplete)'}
                        </span>
                      )}
                      <span className="text-xs text-gray-500">
                        Destination: <strong className="text-gray-800 dark:text-gray-200">{tripState?.destination || 'Requested'}</strong>
                      </span>
                      {/* Detected Attraction Preferences Summary */}
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                        tripState?.preferences?.attraction_preferences?.preference_source === 'explicitly_stated'
                          ? 'bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200 border border-amber-300 dark:border-amber-800'
                          : 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60'
                      }`}>
                        <Sparkles className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                        {tripState?.preferences?.attraction_preferences?.summary_label ||
                          (tripState?.preferences?.interests && tripState.preferences.interests.length > 0
                            ? `Your interests: ${tripState.preferences.interests.join(', ')}`
                            : 'Balanced selection of popular local attractions')}
                      </span>

                      {/* Detected Trip Pace Summary */}
                      {(tripState?.preferences?.pace_preferences || (packages[0] && packages[0].trip_pace)) && (
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                          (tripState?.preferences?.pace_preferences?.pace || packages[0]?.trip_pace) === 'RUSHED'
                            ? 'bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-200 border border-amber-300 dark:border-amber-800'
                            : (tripState?.preferences?.pace_preferences?.pace || packages[0]?.trip_pace) === 'SLOW'
                            ? 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200 border border-emerald-300 dark:border-emerald-800'
                            : 'bg-indigo-50 text-indigo-900 dark:bg-indigo-950/60 dark:text-indigo-200 border border-indigo-200 dark:border-indigo-800/60'
                        }`}>
                          <span>{(tripState?.preferences?.pace_preferences?.pace || packages[0]?.trip_pace) === 'RUSHED' ? '⚡' : (tripState?.preferences?.pace_preferences?.pace || packages[0]?.trip_pace) === 'SLOW' ? '🌿' : '⚖️'}</span>
                          <span>{tripState?.preferences?.pace_preferences?.summary_label || `${(tripState?.preferences?.pace_preferences?.pace || packages[0]?.trip_pace || 'Balanced')} Pace`}</span>
                        </span>
                      )}
                    </div>
                    <h2 className="text-3xl font-black text-gray-900 dark:text-white mt-1 tracking-tight">
                      Compare Travel Packages
                    </h2>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 max-w-2xl leading-relaxed">
                      Each package shows its own budget status, calculated from the provider quotes for its selected flights and hotel. Open one to review the itinerary and swap flight or hotel options.
                    </p>
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      onClick={saveTrip}
                      className="px-4 py-2.5 rounded-xl bg-purple-100 hover:bg-purple-200 dark:bg-purple-900/40 dark:hover:bg-purple-800/60 text-purple-700 dark:text-purple-300 font-bold text-xs transition-colors"
                    >
                      Save All Packages
                    </button>
                    <button
                      onClick={resetResults}
                      className="px-4 py-2.5 rounded-xl bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 font-bold text-xs transition-colors"
                    >
                      Plan New Trip
                    </button>
                  </div>
                </div>

                {restored && (
                  <div className="p-4 rounded-2xl bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800 text-xs text-sky-900 dark:text-sky-200" role="status">
                    Showing results restored from this browser. Changing options needs the original search session on the server; if it has expired you will be asked to run the search again.
                  </div>
                )}

                {providerProblems.length > 0 && (
                  <div className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-200 space-y-1" role="status">
                    <div className="font-bold">Partial results: some searches did not fully succeed</div>
                    {providerProblems.map((s, i) => (
                      <div key={i}>{s?.capability || 'Search'}: {s?.status}{s?.error_detail ? ` — ${s.error_detail}` : ''}</div>
                    ))}
                  </div>
                )}

                {packageNotes.length > 0 && (
                  <div className="p-4 rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 flex items-start gap-3">
                    <Info className="w-5 h-5 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
                    <div className="text-xs text-indigo-900 dark:text-indigo-200 space-y-1">
                      <span className="font-bold block">Package notes:</span>
                      {packageNotes.map((note, i) => (
                        <div key={i}>{note}</div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  {packages.map((pkg) => (
                    <PackageCard
                      key={pkg.package_id}
                      pkg={pkg}
                      onSelect={(pkgId) => setSelectedPackageId(pkgId)}
                    />
                  ))}
                </div>

                {itinerary?.provider_statuses && (
                  <div className="p-6 rounded-2xl bg-gray-100/80 dark:bg-gray-900/60 border border-gray-200 dark:border-gray-800">
                    <h4 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">
                      Provider Search Status
                    </h4>
                    <div className="flex flex-wrap gap-3">
                      {Object.values(itinerary.provider_statuses).filter(Boolean).map((s, i) => (
                        <div key={i} className="flex flex-col gap-0.5">
                          <span
                            className={`text-xs px-2.5 py-1 rounded-full border w-fit font-medium ${
                              s.status === 'success'
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800'
                                : s.status === 'error'
                                ? 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800'
                                : 'bg-gray-100 text-gray-600 border-gray-300 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700'
                            }`}
                          >
                            {s.capability}: {s.status}
                          </span>
                          {s.error_detail && (
                            <span className="text-[10px] text-rose-500 max-w-[200px] truncate">
                              {s.error_detail}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* View B: Detailed Inspection & Customization View for a Single Package */}
            {selectedPackageId && activePackage && (
              <PackageDetails
                pkg={activePackage}
                allPackages={packages}
                onBack={() => {
                  setSelectedPackageId(null);
                  setSelectionError(null);
                }}
                onSwitchPackage={(newPkgId) => {
                  setSelectedPackageId(newPkgId);
                  setSelectionError(null);
                }}
                onSelectOutboundFlight={(id, f) => changeSelection(id, { outbound_flight_id: f.option_id })}
                onSelectReturnFlight={(id, f) => changeSelection(id, { return_flight_id: f.option_id })}
                onSelectHotel={(id, h) => changeSelection(id, { hotel_id: h.hotel_id })}
                onSaveTrip={saveTrip}
                isUpdating={updatingPackageId === activePackage.package_id}
                selectionError={selectionError}
                selectionDisabledReason={selectionDisabledReason}
                seasonalWeather={itinerary?.seasonal_weather}
              />
            )}
          </div>
        )}
      </main>
    </div>
  );
}
