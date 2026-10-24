import { useState, useEffect } from 'react';
import {
  LifeBuoy, AlertOctagon, CheckCircle2, Megaphone, MapPin, Key,
  ShieldAlert, RefreshCw, CheckCheck, Clock, FileText,
  Sparkles, Trash2
} from 'lucide-react';
import { apiRequest } from '../api/client';
import type { Case, SanitationTicket, RateCard, ScamReport, AuditLog } from '../types';

export const HelpdeskDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'child_safety' | 'sanitation' | 'services' | 'audit'>('child_safety');
  const [cases, setCases] = useState<Case[]>([]);
  const [sanitationTickets, setSanitationTickets] = useState<SanitationTicket[]>([]);
  const [rateCards, setRateCards] = useState<RateCard[]>([]);
  const [scamReports, setScamReports] = useState<ScamReport[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Handover modal state
  const [selectedCaseForHandover, setSelectedCaseForHandover] = useState<Case | null>(null);
  const [handoverPin, setHandoverPin] = useState('');
  const [useFallback, setUseFallback] = useState(false);
  const [fallbackMethod, setFallbackMethod] = useState('SUPERVISOR_APPROVED_FALLBACK');
  const [witnessStaffName, setWitnessStaffName] = useState('Officer K. Lakshmi');
  const [guardianNameVerified, setGuardianNameVerified] = useState('');
  const [guardianPhoneVerified, setGuardianPhoneVerified] = useState('');
  const [handoverNotes, setHandoverNotes] = useState('');
  const [handoverError, setHandoverError] = useState<string | null>(null);

  // Missing Child Modal state
  const [showMissingModal, setShowMissingModal] = useState(false);
  const [missingChildName, setMissingChildName] = useState('');
  const [missingChildAge, setMissingChildAge] = useState<number | undefined>(undefined);
  const [missingClothing, setMissingClothing] = useState('');
  const [missingLastSeen, setMissingLastSeen] = useState('Pushkar Ghat Main Steps');
  const [missingBandId, setMissingBandId] = useState('');
  const [missingGuardianPhone, setMissingGuardianPhone] = useState('');

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === 'child_safety') {
        const data = await apiRequest<Case[]>('/cases');
        setCases(data);
      } else if (activeTab === 'sanitation') {
        const data = await apiRequest<SanitationTicket[]>('/sanitation/tickets');
        setSanitationTickets(data);
      } else if (activeTab === 'services') {
        const [rates, scams] = await Promise.all([
          apiRequest<RateCard[]>('/services/rate-cards'),
          apiRequest<ScamReport[]>('/services/scam-reports'),
        ]);
        setRateCards(rates);
        setScamReports(scams);
      } else if (activeTab === 'audit') {
        const logs = await apiRequest<AuditLog[]>('/audit/logs');
        setAuditLogs(logs);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleHandoverSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCaseForHandover) return;
    setHandoverError(null);
    setLoading(true);

    try {
      await apiRequest(`/cases/${selectedCaseForHandover.id}/verify-handover`, {
        method: 'POST',
        body: JSON.stringify({
          pin: useFallback ? undefined : handoverPin,
          fallback_method: useFallback ? fallbackMethod : undefined,
          witness_staff_name: witnessStaffName,
          guardian_name_verified: guardianNameVerified,
          guardian_phone_verified: guardianPhoneVerified,
          notes: handoverNotes,
        }),
      });

      setSelectedCaseForHandover(null);
      setHandoverPin('');
      setUseFallback(false);
      setHandoverNotes('');
      loadData();
    } catch (err: any) {
      setHandoverError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleMissingChildSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await apiRequest('/cases/missing-child', {
        method: 'POST',
        body: JSON.stringify({
          child_name: missingChildName,
          child_age: missingChildAge,
          clothing_description: missingClothing,
          last_seen_location: missingLastSeen,
          band_id: missingBandId || undefined,
          guardian_phone: missingGuardianPhone,
        }),
      });
      setShowMissingModal(false);
      setMissingChildName('');
      setMissingClothing('');
      setMissingBandId('');
      setMissingGuardianPhone('');
      loadData();
    } catch (err: any) {
      alert(`Error creating missing child alert: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSanitationUpdate = async (ticketId: number, status: string, isReopen = false) => {
    try {
      await apiRequest(`/sanitation/tickets/${ticketId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status,
          is_reopened: isReopen,
          supervisor_notes: isReopen ? 'Supervisor flagged incomplete cleaning.' : 'Supervisor verified cleanliness.',
        }),
      });
      loadData();
    } catch (err: any) {
      alert(`Sanitation update failed: ${err.message}`);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center bg-white p-6 rounded-2xl border border-slate-200 shadow-xs gap-4">
        <div>
          <div className="flex items-center gap-2">
            <LifeBuoy className="w-6 h-6 text-red-600" />
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Helpdesk & Operations Command
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Authorised Helpdesk, Police Liaison & Zonal Operations • Real-time cases, guardian alerts, and verified handovers.
          </p>
        </div>

        {/* Navigation Tabs */}
        <div className="flex bg-slate-100 p-1 rounded-xl text-xs font-semibold">
          <button
            onClick={() => setActiveTab('child_safety')}
            className={`px-3.5 py-2 rounded-lg transition flex items-center gap-1.5 ${activeTab === 'child_safety' ? 'bg-white text-red-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <ShieldAlert className="w-4 h-4 text-red-600" />
            Child Safety Cases ({cases.length})
          </button>
          <button
            onClick={() => setActiveTab('sanitation')}
            className={`px-3.5 py-2 rounded-lg transition flex items-center gap-1.5 ${activeTab === 'sanitation' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <Trash2 className="w-4 h-4 text-indigo-600" />
            Sanitation Dispatch ({sanitationTickets.length})
          </button>
          <button
            onClick={() => setActiveTab('services')}
            className={`px-3.5 py-2 rounded-lg transition flex items-center gap-1.5 ${activeTab === 'services' ? 'bg-white text-emerald-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <Sparkles className="w-4 h-4 text-emerald-600" />
            Rates & Scams ({scamReports.length})
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            className={`px-3.5 py-2 rounded-lg transition flex items-center gap-1.5 ${activeTab === 'audit' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <FileText className="w-4 h-4" />
            Audit Logs
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-xl text-xs flex items-center gap-2">
          <AlertOctagon className="w-4 h-4 text-red-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* TAB 1: CHILD SAFETY & ACTIVE CASES */}
      {activeTab === 'child_safety' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center bg-white p-4 rounded-xl border border-slate-200">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Active Reunification & Missing Child Grid</h2>
              <p className="text-xs text-slate-500">
                Track lost/found reports, view last-known scan clues, broadcast Telugu PA scripts, and conduct verified handovers.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowMissingModal(true)}
                className="px-3.5 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 transition shadow-xs"
              >
                <AlertOctagon className="w-3.5 h-3.5" />
                Report Missing Child (BOLO)
              </button>
              <button
                onClick={loadData}
                className="p-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition"
                title="Refresh"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {cases.map((c) => (
              <div
                key={c.id}
                className={`bg-white rounded-2xl border p-5 shadow-xs space-y-4 text-xs transition ${c.status === 'RESOLVED' ? 'border-slate-200 opacity-75' : 'border-red-300 ring-2 ring-red-100'}`}
              >
                <div className="flex flex-wrap justify-between items-start gap-2 border-b border-slate-100 pb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono font-black text-sm bg-slate-900 text-white px-2.5 py-0.5 rounded-md">
                      {c.case_number}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${c.case_type === 'FOUND_CHILD' ? 'bg-amber-100 text-amber-900' : 'bg-red-100 text-red-900'}`}>
                      {c.case_type.replace('_', ' ')}
                    </span>
                    {c.band_id && (
                      <span className="font-mono font-bold bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded border border-indigo-200">
                        Band: {c.band_id}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${c.status === 'RESOLVED' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-600 text-white animate-pulse'}`}>
                      {c.status}
                    </span>
                    {c.status !== 'RESOLVED' && (
                      <button
                        onClick={() => {
                          setSelectedCaseForHandover(c);
                          setGuardianNameVerified(c.reported_by_name?.replace('Guardian (', '').replace(')', '') || '');
                        }}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold text-xs flex items-center gap-1 transition shadow-xs"
                      >
                        <Key className="w-3 h-3" />
                        Verify Handover
                      </button>
                    )}
                  </div>
                </div>

                {/* Case Info Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="space-y-1">
                    <div className="text-[10px] font-bold uppercase text-slate-400">Reporter & Location</div>
                    <div className="font-semibold text-slate-800">{c.reported_by_name || 'Anonymous'}</div>
                    <div className="text-slate-600 flex items-center gap-1">
                      <MapPin className="w-3 h-3 text-red-500 shrink-0" />
                      {c.location_name || 'Ghat Zone'}
                    </div>
                    {c.latitude && (
                      <div className="text-[10px] text-slate-400 font-mono">
                        GPS Fix: {c.latitude.toFixed(4)}, {c.longitude?.toFixed(4)} (±{c.location_accuracy}m)
                      </div>
                    )}
                  </div>

                  <div className="space-y-1">
                    <div className="text-[10px] font-bold uppercase text-slate-400">Guardian Notification Status</div>
                    {c.notification_attempts.length === 0 ? (
                      <div className="text-slate-400 italic">No alerts queued</div>
                    ) : (
                      c.notification_attempts.map((na) => (
                        <div key={na.id} className="p-2 bg-slate-50 rounded-lg border border-slate-200 space-y-0.5">
                          <div className="flex justify-between items-center text-[11px] font-semibold">
                            <span className="font-mono">{na.recipient_phone}</span>
                            <span className="text-emerald-700 flex items-center gap-0.5">
                              <CheckCheck className="w-3 h-3 text-emerald-600" />
                              {na.status}
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-500 truncate">{na.message_content}</div>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="space-y-1">
                    <div className="text-[10px] font-bold uppercase text-slate-400">Assignment & Timing</div>
                    <div className="text-slate-700">Assigned: <strong>{c.assigned_to_name || 'Pending Runner'}</strong></div>
                    <div className="text-slate-500 flex items-center gap-1">
                      <Clock className="w-3 h-3 text-slate-400" />
                      Reported: {new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                    {c.handover_method && (
                      <div className="text-emerald-700 font-semibold mt-1">
                        Handover: {c.handover_method}
                      </div>
                    )}
                  </div>
                </div>

                {/* Telugu Public Address Announcement Script */}
                {c.telugu_announcement_script && (
                  <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-xl space-y-1">
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-amber-900 flex items-center gap-1 text-[11px]">
                        <Megaphone className="w-3.5 h-3.5 text-amber-600" />
                        Telugu Public Address (PA) Broadcast Announcement Script:
                      </span>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(c.telugu_announcement_script!);
                          alert('Telugu announcement script copied to clipboard!');
                        }}
                        className="text-[10px] bg-amber-200 hover:bg-amber-300 text-amber-900 px-2 py-0.5 rounded font-semibold transition"
                      >
                        Copy Script
                      </button>
                    </div>
                    <p className="text-slate-800 leading-relaxed font-sans text-xs">
                      {c.telugu_announcement_script}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: SANITATION DISPATCH */}
      {activeTab === 'sanitation' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-base font-bold text-slate-900">Sanitation & Cleanliness Dispatch Grid</h2>
              <p className="text-xs text-slate-500">
                Facility QR complaints, rapid team assignment, photo proof validation, and supervisor sign-off.
              </p>
            </div>
            <button onClick={loadData} className="p-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-slate-50 text-slate-500 border-b border-slate-200 font-bold uppercase tracking-wider">
                  <th className="p-3">Ticket</th>
                  <th className="p-3">Facility</th>
                  <th className="p-3">Issue</th>
                  <th className="p-3">Priority</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Team Assigned</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sanitationTickets.map((st) => (
                  <tr key={st.id} className="hover:bg-slate-50 transition">
                    <td className="p-3 font-mono font-bold text-slate-900">{st.ticket_number}</td>
                    <td className="p-3">
                      <div className="font-semibold text-slate-800">{st.facility_name}</div>
                      <div className="text-[10px] text-slate-400">{st.ghat_name}</div>
                    </td>
                    <td className="p-3 text-slate-700">{st.issue_type}</td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${st.priority === 'URGENT' ? 'bg-red-100 text-red-800' : 'bg-slate-100 text-slate-800'}`}>
                        {st.priority}
                      </span>
                    </td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${st.status === 'RESOLVED_VERIFIED' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                        {st.status}
                      </span>
                    </td>
                    <td className="p-3 text-slate-600">{st.assigned_team || 'Pending'}</td>
                    <td className="p-3 text-right space-x-2">
                      {st.status !== 'RESOLVED_VERIFIED' && (
                        <button
                          onClick={() => handleSanitationUpdate(st.id, 'RESOLVED_VERIFIED')}
                          className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-bold text-[11px] transition"
                        >
                          Approve Cleaned
                        </button>
                      )}
                      <button
                        onClick={() => handleSanitationUpdate(st.id, 'REOPENED', true)}
                        className="px-2 py-1 bg-amber-100 hover:bg-amber-200 text-amber-800 rounded font-semibold text-[11px] transition"
                      >
                        Reopen
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: VERIFIED SERVICES & SCAMS */}
      {activeTab === 'services' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Rate Cards */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
            <h2 className="text-base font-bold text-slate-900">Official Authority-Approved Rate Cards</h2>
            <p className="text-xs text-slate-500">
              Verified fares published by East Godavari District Collectorate & RTA.
            </p>
            <div className="space-y-3">
              {rateCards.map((rc) => (
                <div key={rc.id} className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1 text-xs">
                  <div className="flex justify-between items-center font-bold text-slate-900">
                    <span>{rc.service_name}</span>
                    <span className="text-indigo-700 font-mono text-sm">₹{rc.approved_rate}</span>
                  </div>
                  <div className="text-[11px] text-slate-500">{rc.unit} • {rc.verified_by_authority}</div>
                  {rc.notes && <div className="text-[10px] text-slate-600 italic">{rc.notes}</div>}
                </div>
              ))}
            </div>
          </div>

          {/* Scam Reports */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
            <h2 className="text-base font-bold text-slate-900">Citizen Overcharging & Scam Reports</h2>
            <p className="text-xs text-slate-500">
              Forwarded directly to Special Revenue & Police Flying Squads.
            </p>
            <div className="space-y-3">
              {scamReports.map((sr) => (
                <div key={sr.id} className="p-3 bg-red-50/40 border border-red-200 rounded-xl space-y-1 text-xs">
                  <div className="flex justify-between items-center font-bold text-red-900">
                    <span>{sr.service_category} ({sr.service_provider_identifier || 'Unidentified'})</span>
                    <span className="text-red-700 font-mono">Demanded: ₹{sr.demanded_amount} (Official: ₹{sr.official_amount})</span>
                  </div>
                  <div className="text-slate-700">{sr.details}</div>
                  <div className="text-[10px] text-slate-500">
                    Location: {sr.location} • Status: <strong className="text-red-800">{sr.status}</strong>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: AUDIT LOGS */}
      {activeTab === 'audit' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-base font-bold text-slate-900">Immutable Audit & Safeguarding Governance Log</h2>
            <button onClick={loadData} className="p-2 bg-slate-100 hover:bg-slate-200 rounded-lg text-slate-700">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="bg-slate-50 text-slate-500 border-b border-slate-200 uppercase tracking-wider text-[11px]">
                  <th className="p-3">Timestamp</th>
                  <th className="p-3">Action</th>
                  <th className="p-3">Entity</th>
                  <th className="p-3">Actor</th>
                  <th className="p-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50">
                    <td className="p-3 text-slate-500">{new Date(log.created_at).toLocaleTimeString()}</td>
                    <td className="p-3 font-bold text-slate-800">{log.action}</td>
                    <td className="p-3 text-indigo-700">{log.entity_type}: {log.entity_id}</td>
                    <td className="p-3 text-slate-700">{log.actor_name}</td>
                    <td className="p-3 text-slate-500 truncate max-w-sm">{log.details_json}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* VERIFY HANDOVER MODAL */}
      {selectedCaseForHandover && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 bg-emerald-800 text-white flex justify-between items-center">
              <div className="flex items-center gap-2 font-bold text-sm">
                <Key className="w-5 h-5 text-emerald-300" />
                Child Handover Safeguarding Authorization
              </div>
              <button onClick={() => setSelectedCaseForHandover(null)} className="text-white/80 hover:text-white">
                ✕
              </button>
            </div>

            <form onSubmit={handleHandoverSubmit} className="p-6 space-y-4 text-xs">
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 text-[11px]">
                <strong>Mandatory Safeguarding Rule:</strong> The wristband alone is NEVER proof of identity. Staff must either verify the guardian's secret Release PIN or follow the approved supervisor fallback procedure.
              </div>

              {handoverError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-800 rounded-lg font-semibold">
                  {handoverError}
                </div>
              )}

              {/* Mode switch */}
              <div className="flex gap-2 border-b border-slate-200 pb-3">
                <button
                  type="button"
                  onClick={() => setUseFallback(false)}
                  className={`px-3 py-1.5 rounded-lg font-bold transition ${!useFallback ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}`}
                >
                  Standard 4-Digit Release PIN
                </button>
                <button
                  type="button"
                  onClick={() => setUseFallback(true)}
                  className={`px-3 py-1.5 rounded-lg font-bold transition ${useFallback ? 'bg-amber-600 text-white' : 'bg-slate-100 text-slate-700'}`}
                >
                  Safeguarding Fallback (No Phone / Lost PIN)
                </button>
              </div>

              {!useFallback ? (
                <div>
                  <label className="font-bold text-slate-700 block mb-1">
                    Enter Guardian's Secret Release PIN *
                  </label>
                  <input
                    type="password"
                    maxLength={6}
                    required={!useFallback}
                    placeholder="e.g. 4829"
                    value={handoverPin}
                    onChange={(e) => setHandoverPin(e.target.value)}
                    className="w-full px-4 py-2 text-lg font-mono tracking-widest text-center border-2 border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none"
                  />
                  <p className="text-[10px] text-slate-400 mt-1">3 incorrect attempts will automatically lock release.</p>
                </div>
              ) : (
                <div className="space-y-3 bg-amber-50/50 p-3 rounded-xl border border-amber-200">
                  <div>
                    <label className="font-bold text-slate-800 block mb-1">Approved Fallback Method</label>
                    <select
                      value={fallbackMethod}
                      onChange={(e) => setFallbackMethod(e.target.value)}
                      className="w-full px-3 py-1.5 border border-slate-300 rounded-lg bg-white"
                    >
                      <option value="SUPERVISOR_APPROVED_FALLBACK">Supervisor Corroboration & Backup Contact Check</option>
                      <option value="POLICE_ESCALATION">Child Protection / Police Station Escalation</option>
                    </select>
                  </div>
                  <p className="text-[10px] text-slate-600">
                    Contact the registered backup number. Corroborate physical details against registration records before proceeding.
                  </p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Verified Guardian Name *</label>
                  <input
                    type="text"
                    required
                    value={guardianNameVerified}
                    onChange={(e) => setGuardianNameVerified(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Guardian Phone Verified *</label>
                  <input
                    type="tel"
                    required
                    placeholder="e.g. 9848022338"
                    value={guardianPhoneVerified}
                    onChange={(e) => setGuardianPhoneVerified(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Witnessing Staff / Officer Name *</label>
                <input
                  type="text"
                  required
                  value={witnessStaffName}
                  onChange={(e) => setWitnessStaffName(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Handover Observations & Notes</label>
                <textarea
                  rows={2}
                  value={handoverNotes}
                  onChange={(e) => setHandoverNotes(e.target.value)}
                  placeholder="e.g. Verified relationship, emotional recognition confirmed, guardian showed physical ID."
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setSelectedCaseForHandover(null)}
                  className="px-4 py-2 border border-slate-300 rounded-lg font-semibold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold flex items-center gap-1.5 shadow"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Authorize Verified Handover & Close Case
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* REPORT MISSING CHILD MODAL */}
      {showMissingModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
            <div className="px-6 py-4 bg-red-700 text-white flex justify-between items-center">
              <div className="flex items-center gap-2 font-bold text-sm">
                <AlertOctagon className="w-5 h-5 text-red-200" />
                Issue Emergency Missing Child Alert (BOLO)
              </div>
              <button onClick={() => setShowMissingModal(false)} className="text-white/80 hover:text-white">✕</button>
            </div>

            <form onSubmit={handleMissingChildSubmit} className="p-6 space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Child's Name *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Sai Krishna"
                    value={missingChildName}
                    onChange={(e) => setMissingChildName(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Approx. Age</label>
                  <input
                    type="number"
                    placeholder="e.g. 7"
                    value={missingChildAge || ''}
                    onChange={(e) => setMissingChildAge(Number(e.target.value) || undefined)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Clothing & Description *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Yellow t-shirt, blue shorts, brown slippers"
                  value={missingClothing}
                  onChange={(e) => setMissingClothing(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Band ID (if known)</label>
                  <input
                    type="text"
                    placeholder="e.g. BND-XXXXXXXX"
                    value={missingBandId}
                    onChange={(e) => setMissingBandId(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg font-mono uppercase"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Guardian Phone *</label>
                  <input
                    type="tel"
                    required
                    placeholder="e.g. 9848022338"
                    value={missingGuardianPhone}
                    onChange={(e) => setMissingGuardianPhone(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Last Seen Location at Ghats *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Kotilingala Ghat Pillar 14"
                  value={missingLastSeen}
                  onChange={(e) => setMissingLastSeen(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setShowMissingModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg font-semibold hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-bold flex items-center gap-1.5 shadow"
                >
                  <AlertOctagon className="w-4 h-4" />
                  Broadcast BOLO & Generate Telugu Script
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
