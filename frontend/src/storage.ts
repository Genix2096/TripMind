import type { StructuredItinerary, TravelPackage } from './types';

export const ACTIVE_KEY = 'tripmind_active_v2';
export const HISTORY_KEY = 'agentTrip_history';
const ACTIVE_VERSION = 2;

export interface ActiveState {
  version: number;
  savedAt: string;
  sessionId: string | null;
  itinerary: StructuredItinerary | null;
  packages: TravelPackage[];
  packageNotes: string[];
  tripState: any;
  selectedPackageId: string | null;
}

/** JSON replacer: provider `raw` payloads are large and not needed to render or restore results. */
const stripRaw = (key: string, value: unknown) => (key === 'raw' ? undefined : value);

export const isItinerary = (v: any): v is StructuredItinerary =>
  !!v && typeof v === 'object' && typeof v.trip_summary === 'string';

export const isPackage = (p: any): p is TravelPackage =>
  !!p &&
  typeof p === 'object' &&
  typeof p.package_id === 'string' &&
  typeof p.name === 'string' &&
  !!p.budget_report &&
  Array.isArray(p.budget_report.items) &&
  Array.isArray(p.outbound_flight_alternatives) &&
  Array.isArray(p.return_flight_alternatives) &&
  Array.isArray(p.hotel_alternatives) &&
  Array.isArray(p.day_wise) &&
  Array.isArray(p.warnings);

/** Keep only well-formed packages; anything from an older/incompatible shape is dropped. */
export const sanitizePackages = (v: unknown): TravelPackage[] => (Array.isArray(v) ? v.filter(isPackage) : []);

const stringArray = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []);

/** Packages are stored separately, so do not store them twice inside the itinerary. */
const slimItinerary = (it: StructuredItinerary | null): StructuredItinerary | null =>
  it ? { ...it, packages: [] } : null;

export function loadActiveState(): ActiveState | null {
  try {
    const raw = localStorage.getItem(ACTIVE_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw);
    if (!s || s.version !== ACTIVE_VERSION) throw new Error('incompatible');
    const packages = sanitizePackages(s.packages);
    const itinerary = isItinerary(s.itinerary) ? s.itinerary : null;
    if (!itinerary && packages.length === 0) throw new Error('empty');
    const selected = packages.some((p) => p.package_id === s.selectedPackageId) ? s.selectedPackageId : null;
    return {
      version: ACTIVE_VERSION,
      savedAt: typeof s.savedAt === 'string' ? s.savedAt : new Date().toISOString(),
      sessionId: typeof s.sessionId === 'string' ? s.sessionId : null,
      itinerary,
      packages,
      packageNotes: stringArray(s.packageNotes),
      tripState: s.tripState ?? null,
      selectedPackageId: selected,
    };
  } catch {
    try {
      localStorage.removeItem(ACTIVE_KEY);
    } catch {
      /* ignore */
    }
    return null;
  }
}

export function saveActiveState(state: Omit<ActiveState, 'version' | 'savedAt'>): void {
  try {
    const payload: ActiveState = {
      ...state,
      itinerary: slimItinerary(state.itinerary),
      version: ACTIVE_VERSION,
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem(ACTIVE_KEY, JSON.stringify(payload, stripRaw));
  } catch {
    /* storage full or unavailable: persistence is best-effort */
  }
}

export function clearActiveState(): void {
  try {
    localStorage.removeItem(ACTIVE_KEY);
  } catch {
    /* ignore */
  }
}

export function loadHistory(): any[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(parsed) ? parsed.filter((t) => t && typeof t.id === 'string') : [];
  } catch {
    return [];
  }
}

/** Returns false when the browser refused the write (e.g. quota). */
export function saveHistory(trips: any[]): boolean {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(trips, stripRaw));
    return true;
  } catch {
    return false;
  }
}

export function buildHistoryEntry(s: Omit<ActiveState, 'version' | 'savedAt' | 'selectedPackageId'>) {
  return {
    id: Date.now().toString(),
    date: new Date().toISOString(),
    sessionId: s.sessionId,
    itinerary: slimItinerary(s.itinerary),
    packages: s.packages,
    packageNotes: s.packageNotes,
    tripState: s.tripState,
  };
}

/** Normalise a saved trip, including trips saved before packages existed (itinerary only). */
export function normalizeSavedTrip(saved: any) {
  const itinerary = isItinerary(saved?.itinerary) ? saved.itinerary : null;
  const packages = sanitizePackages(saved?.packages ?? itinerary?.packages);
  return {
    itinerary,
    packages,
    packageNotes: stringArray(saved?.packageNotes ?? itinerary?.package_notes),
    tripState: saved?.tripState ?? null,
    sessionId: typeof saved?.sessionId === 'string' ? saved.sessionId : null,
    isLegacy: !!itinerary && packages.length === 0 && saved?.packages === undefined,
  };
}
