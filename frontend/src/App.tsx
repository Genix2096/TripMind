import React, { useState } from 'react';
import { Plane, Calendar, MapPin, Sparkles, Loader2, Info, Navigation, CloudSun, CreditCard, CheckCircle } from 'lucide-react';

interface TripFormProps {
  onSubmit: (request: str) => void;
  isLoading: boolean;
}

const TripForm: React.FC<TripFormProps> = ({ onSubmit, isLoading }) => {
  const [request, setRequest] = useState('');

  return (
    <div className="w-full max-w-2xl mx-auto p-8 rounded-3xl bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl shadow-2xl border border-gray-200 dark:border-gray-700">
      <h2 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-blue-500 mb-6 flex items-center gap-3">
        <Sparkles className="w-8 h-8 text-purple-500" />
        Dream Your Next Trip
      </h2>
      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Describe your ideal trip in natural language
          </label>
          <textarea 
            rows={5}
            className="w-full px-4 py-3 rounded-2xl bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 focus:ring-4 focus:ring-purple-500/20 focus:border-purple-500 outline-none transition-all resize-none text-gray-900 dark:text-gray-100"
            placeholder="e.g., I want to go from New York to London for a week starting next Monday. It's my honeymoon and my budget is $5000. We love historic sites and nice hotels."
            value={request}
            onChange={(e) => setRequest(e.target.value)}
          />
        </div>
        
        <button
          onClick={() => onSubmit(request)}
          disabled={!request.trim() || isLoading}
          className="w-full py-4 rounded-2xl bg-gradient-to-r from-purple-600 to-blue-600 text-white font-bold text-lg shadow-lg hover:shadow-xl hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-6 h-6 animate-spin" />
              Planning...
            </>
          ) : (
            <>
              <Plane className="w-6 h-6" />
              Plan My Trip
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
    case 'understanding': return <Info className="w-5 h-5" />;
    case 'flight_research': return <Plane className="w-5 h-5" />;
    case 'hotel_research': return <MapPin className="w-5 h-5" />;
    case 'attractions': return <Sparkles className="w-5 h-5" />;
    case 'routing': return <Navigation className="w-5 h-5" />;
    case 'weather': return <CloudSun className="w-5 h-5" />;
    case 'budget': return <CreditCard className="w-5 h-5" />;
    case 'synthesis': return <CheckCircle className="w-5 h-5" />;
    default: return <Loader2 className="w-5 h-5 animate-spin" />;
  }
};

const PlanningProgress = ({ events, isComplete }: { events: ProgressEvent[], isComplete: boolean }) => {
  return (
    <div className="w-full max-w-2xl mx-auto mt-8 space-y-4">
      {events.map((e, idx) => (
        <div key={idx} className="p-4 rounded-2xl bg-white dark:bg-gray-800 shadow-sm flex items-start gap-4 animate-in slide-in-from-bottom-2 fade-in duration-300">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded-xl">
            <StageIcon stage={e.stage} />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 capitalize">{e.stage.replace('_', ' ')}</h3>
            <p className="text-gray-600 dark:text-gray-400 text-sm mt-1">{e.message}</p>
          </div>
        </div>
      ))}
      {!isComplete && events.length > 0 && (
        <div className="p-4 flex items-center justify-center gap-2 text-gray-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Working...</span>
        </div>
      )}
    </div>
  );
};

export default function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [result, setResult] = useState<any>(null);
  
  // Local storage history
  const [savedTrips, setSavedTrips] = useState<any[]>(() => {
    const saved = localStorage.getItem('agentTrip_history');
    return saved ? JSON.parse(saved) : [];
  });

  const saveTrip = () => {
    if (!result) return;
    const newTrip = {
      id: Date.now().toString(),
      date: new Date().toISOString(),
      itinerary: result
    };
    const updated = [newTrip, ...savedTrips];
    setSavedTrips(updated);
    localStorage.setItem('agentTrip_history', JSON.stringify(updated));
    alert('Trip saved locally!');
  };

  const deleteTrip = (id: string) => {
    const updated = savedTrips.filter(t => t.id !== id);
    setSavedTrips(updated);
    localStorage.setItem('agentTrip_history', JSON.stringify(updated));
  };

  const loadTrip = (trip: any) => {
    setResult(trip.itinerary);
    setEvents([]);
    setIsComplete(true);
  };

  const [tripStateForClarification, setTripStateForClarification] = useState<any>(null);
  const [clarificationQuestion, setClarificationQuestion] = useState<string | null>(null);

  const handleSubmit = async (request: string, existingState: any = null) => {
    setIsLoading(true);
    if (!existingState) {
        setEvents([]);
    }
    setIsComplete(false);
    setResult(null);
    setClarificationQuestion(null);

    try {
      const response = await fetch('http://localhost:8000/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            request, 
            existing_state: existingState ? JSON.stringify(existingState) : null 
        }),
      });
      
      const { session_id } = await response.json();
      
      const eventSource = new EventSource(`http://localhost:8000/api/plan/${session_id}/stream`);
      
      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setEvents(prev => [...prev, data]);
        
        if (data.stage === 'completed' || data.stage === 'error' || data.stage === 'clarification_needed') {
          eventSource.close();
          setIsComplete(true);
          setIsLoading(false);
          
          if (data.stage === 'completed') {
            setResult(data.data.itinerary);
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
        setEvents(prev => [...prev, { stage: 'error', message: 'Connection to server lost.' }]);
      };
      
    } catch (e) {
      setIsLoading(false);
      setIsComplete(true);
      setEvents(prev => [...prev, { stage: 'error', message: 'Failed to start planning session.' }]);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 p-8">
      <header className="max-w-6xl mx-auto mb-12 flex justify-between items-center">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Plane className="w-8 h-8 text-purple-600" />
          AgentTrip
        </h1>
        {savedTrips.length > 0 && (
          <div className="flex gap-2">
            <select 
              className="bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg px-3 py-2 text-sm"
              onChange={(e) => {
                if (e.target.value) {
                  const trip = savedTrips.find(t => t.id === e.target.value);
                  if (trip) loadTrip(trip);
                  e.target.value = ""; // reset
                }
              }}
            >
              <option value="">Load Saved Trip...</option>
              {savedTrips.map(t => (
                <option key={t.id} value={t.id}>{new Date(t.date).toLocaleDateString()}</option>
              ))}
            </select>
            <button 
              onClick={() => {
                if (confirm('Clear all saved trips?')) {
                  setSavedTrips([]);
                  localStorage.removeItem('agentTrip_history');
                }
              }}
              className="text-red-500 text-sm font-medium hover:underline px-3 py-2"
            >
              Clear All
            </button>
          </div>
        )}
      </header>
      
      <main className="max-w-6xl mx-auto">
        {!result && (
          <TripForm onSubmit={handleSubmit} isLoading={isLoading} />
        )}
        
        {(events.length > 0 && !result) && (
          <div className="flex flex-col space-y-6">
            <PlanningProgress events={events} isComplete={isComplete} />
            {clarificationQuestion && (
              <div className="w-full max-w-2xl mx-auto p-6 rounded-2xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 shadow-md">
                <h3 className="text-xl font-bold text-amber-800 dark:text-amber-300 mb-2 flex items-center gap-2">
                  <Info className="w-6 h-6" /> Need More Info
                </h3>
                <p className="text-gray-700 dark:text-gray-300 mb-4">{clarificationQuestion}</p>
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
                    placeholder="Type your reply here..." 
                    className="flex-1 px-4 py-3 rounded-xl bg-white dark:bg-gray-800 border border-amber-300 dark:border-amber-700 focus:ring-2 focus:ring-amber-500 outline-none text-gray-900 dark:text-gray-100"
                    autoFocus
                  />
                  <button 
                    type="submit" 
                    disabled={isLoading}
                    className="px-6 py-3 rounded-xl bg-amber-500 hover:bg-amber-600 text-white font-bold transition-colors disabled:opacity-50"
                  >
                    Reply
                  </button>
                </form>
              </div>
            )}
          </div>
        )}
        
        {result && typeof result === 'object' && (
          <div className="w-full max-w-4xl mx-auto space-y-8 relative">
            <div className="absolute top-4 right-4 flex gap-2">
               <button 
                onClick={saveTrip}
                className="px-4 py-2 bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300 rounded-lg text-sm font-semibold hover:bg-purple-200 dark:hover:bg-purple-800/50 transition-colors shadow-sm"
              >
                Save Locally
              </button>
            </div>
            
            <div className="p-8 rounded-3xl bg-white dark:bg-gray-800 shadow-xl">
              <h2 className="text-3xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-blue-500">Your Itinerary</h2>
              <p className="text-lg text-gray-700 dark:text-gray-300 mb-8 leading-relaxed">
                {result.trip_summary}
              </p>
              
              {result.validation_warnings && result.validation_warnings.length > 0 && (
                <div className="mb-8 p-4 bg-orange-50 dark:bg-orange-900/30 rounded-xl border border-orange-200 dark:border-orange-800">
                  <h3 className="font-semibold text-orange-800 dark:text-orange-300 flex items-center gap-2 mb-2">
                    <Info className="w-5 h-5" /> Important Notes
                  </h3>
                  <ul className="list-disc pl-5 text-orange-700 dark:text-orange-400 space-y-1">
                    {result.validation_warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              )}
              
              <div className="space-y-6">
                <h3 className="text-2xl font-bold border-b border-gray-100 dark:border-gray-700 pb-2">Daily Plan</h3>
                {result.day_wise && result.day_wise.map((day: any, idx: number) => (
                  <div key={idx} className="bg-gray-50 dark:bg-gray-700/50 p-6 rounded-2xl">
                    <h4 className="text-xl font-bold mb-2 flex items-center justify-between">
                      <span>Day {idx + 1}: {day.title}</span>
                      {day.date && <span className="text-sm font-normal text-gray-500 dark:text-gray-400">{new Date(day.date).toLocaleDateString()}</span>}
                    </h4>
                    {day.weather_summary && (
                      <p className="text-sm text-blue-600 dark:text-blue-400 mb-4 flex items-center gap-1">
                        <CloudSun className="w-4 h-4" /> {day.weather_summary}
                      </p>
                    )}
                    
                    <ul className="space-y-4">
                      {day.activities.map((act: any, i: number) => (
                        <li key={i} className="flex items-start gap-3 bg-white dark:bg-gray-800 p-4 rounded-xl border border-gray-100 dark:border-gray-700 shadow-sm">
                          <span className="mt-1.5 w-2.5 h-2.5 rounded-full bg-purple-500 shrink-0"></span>
                          <div className="flex-1">
                            <h5 className="font-bold text-gray-900 dark:text-gray-100">{act.name}</h5>
                            {act.description && <p className="text-gray-600 dark:text-gray-400 text-sm mt-1">{act.description}</p>}
                            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-2 text-xs text-gray-500 dark:text-gray-400">
                              {act.location && <span className="flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> {act.location}</span>}
                              {act.time_window && <span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> {act.time_window}</span>}
                              {act.travel_info && <span className="flex items-center gap-1"><Navigation className="w-3.5 h-3.5" /> {act.travel_info}</span>}
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                    
                    {day.missing_information && day.missing_information.length > 0 && (
                      <div className="mt-4 text-sm text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 p-3 rounded-xl">
                        <strong>Note:</strong> {day.missing_information.join(", ")}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              
              {result.flights && result.flights.length > 0 && (
                <div className="mt-8">
                  <h3 className="text-xl font-bold mb-4 flex items-center gap-2"><Plane className="w-5 h-5 text-blue-500" /> Flight Options</h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    {result.flights.map((f: any) => (
                      <div key={f.option_id} className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
                         <div className="font-semibold">{f.segments[0].departure.code} → {f.segments[f.segments.length-1].arrival.code}</div>
                         <div className="text-sm text-gray-500 mt-1">{f.price ? `${f.price.currency === 'INR' ? '₹' : f.price.currency + ' '}${f.price.amount}` : "Price unknown"}</div>
                         <div className="text-xs text-gray-400 mt-2">via {f.segments[0].airline}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {result.hotels && result.hotels.length > 0 && (
                <div className="mt-8">
                  <h3 className="text-xl font-bold mb-4 flex items-center gap-2"><MapPin className="w-5 h-5 text-emerald-500" /> Hotel Options</h3>
                  <div className="grid gap-4 md:grid-cols-2">
                    {result.hotels.map((h: any, i: number) => (
                      <div key={i} className="p-4 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50">
                         <div className="font-semibold">{h.name}</div>
                         <div className="text-sm text-gray-500 mt-1">{h.nightly_rate ? (h.nightly_rate.amount ? `${h.nightly_rate.amount.currency === 'INR' ? '₹' : h.nightly_rate.amount.currency + ' '}${h.nightly_rate.amount.amount} / night` : h.nightly_rate.display_text) : "Price unknown"}</div>
                         <div className="text-xs text-gray-400 mt-2">{h.rating} stars</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {result.provider_statuses && (
                <div className="mt-8 p-4 bg-gray-100 dark:bg-gray-900 rounded-xl">
                  <h4 className="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">System Status</h4>
                  <div className="flex flex-wrap gap-4">
                    {Object.values(result.provider_statuses).map((s: any, i: number) => (
                       <div key={i} className="flex flex-col gap-1">
                         <span className={`text-xs px-2 py-1 rounded-full border w-fit ${s.status === 'success' ? 'bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:border-green-800' : s.status === 'error' ? 'bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:border-red-800' : 'bg-gray-200 text-gray-600 border-gray-300 dark:bg-gray-700 dark:text-gray-400 dark:border-gray-600'}`}>
                           {s.capability}: {s.status}
                         </span>
                         {s.error_detail && <span className="text-[10px] text-red-500 max-w-[200px] break-words leading-tight">{s.error_detail}</span>}
                       </div>
                    ))}
                  </div>
                </div>
              )}
              
              <div className="mt-8 pt-6 border-t border-gray-100 dark:border-gray-700">
                <button 
                  onClick={() => {
                    setResult(null);
                    setEvents([]);
                    setIsComplete(false);
                  }}
                  className="px-6 py-3 bg-gray-100 dark:bg-gray-700 rounded-xl font-medium hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors w-full sm:w-auto text-center"
                >
                  Plan Another Trip
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
