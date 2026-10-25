import { useState, useEffect } from 'react';
import {
  Users, Search, CheckCircle, Printer, Key, Plus, ShieldCheck,
  AlertTriangle, RefreshCw, UserCheck, Phone, Tag
} from 'lucide-react';
import { apiRequest } from '../api/client';
import type { FamilyCluster } from '../types';
import { PrintLabelModal } from './PrintLabelModal';

export const RegistrationDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'pending' | 'walkin' | 'clusters'>('pending');
  const [pendingClusters, setPendingClusters] = useState<FamilyCluster[]>([]);
  const [clusters, setClusters] = useState<FamilyCluster[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedBandForPrint, setSelectedBandForPrint] = useState<string | null>(null);

  // Walk-in form state
  const [guardianName, setGuardianName] = useState('');
  const [primaryPhone, setPrimaryPhone] = useState('');
  const [backupPhone, setBackupPhone] = useState('');
  const [bandsCount, setBandsCount] = useState(2);
  const [memberDetails, setMemberDetails] = useState('');
  const [successInfo, setSuccessInfo] = useState<{ clusterCode: string; pin: string; bands: any[] } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    setActionError(null);
    try {
      if (activeTab === 'pending') {
        const data = await apiRequest<FamilyCluster[]>('/registration/pending');
        setPendingClusters(data);
      } else if (activeTab === 'clusters') {
        const data = await apiRequest<FamilyCluster[]>(`/registration/clusters${searchQuery ? `?search=${encodeURIComponent(searchQuery)}` : ''}`);
        setClusters(data);
      }
    } catch (err: any) {
      setActionError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleClaimPending = async (regRef: string) => {
    setActionError(null);
    setLoading(true);
    try {
      const res = await apiRequest(`/registration/claim-pending/${regRef}`, { method: 'POST' });
      setSuccessInfo({
        clusterCode: res.cluster_code,
        pin: res.release_pin,
        bands: res.bands,
      });
      loadData();
    } catch (err: any) {
      setActionError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleWalkInSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    setLoading(true);

    try {
      const members = memberDetails
        .split(';')
        .map((m) => m.trim())
        .filter(Boolean)
        .map((m) => ({ name: m, relation: 'Family Member' }));

      const res = await apiRequest('/registration/cluster', {
        method: 'POST',
        body: JSON.stringify({
          primary_guardian_name: guardianName,
          primary_phone: primaryPhone,
          backup_phone: backupPhone || undefined,
          bands_count: Number(bandsCount),
          members: members.length > 0 ? members : [{ name: guardianName, relation: 'Guardian' }],
          notes: 'Assisted walk-in counter registration',
        }),
      });

      setSuccessInfo({
        clusterCode: res.cluster_code,
        pin: res.release_pin,
        bands: res.bands,
      });

      // Reset form
      setGuardianName('');
      setPrimaryPhone('');
      setBackupPhone('');
      setBandsCount(2);
      setMemberDetails('');
    } catch (err: any) {
      setActionError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateBandStatus = async (bandId: string, newStatus: string) => {
    try {
      await apiRequest(`/registration/bands/${bandId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      });
      loadData();
    } catch (err: any) {
      alert(`Failed to update band status: ${err.message}`);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center bg-white p-6 rounded-2xl border border-slate-200 shadow-xs gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Tag className="w-6 h-6 text-indigo-600" />
            <h1 className="text-2xl font-black text-slate-900 tracking-tight">
              Registration & Wristband Issuance Grid
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Authorised counter operator portal for Godavari Pushkaralu 2027 • Family-cluster linking, QR label generation, and Release PIN distribution.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex bg-slate-100 p-1 rounded-xl text-xs font-semibold">
          <button
            onClick={() => { setActiveTab('pending'); setSuccessInfo(null); }}
            className={`px-4 py-2 rounded-lg transition flex items-center gap-1.5 ${activeTab === 'pending' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <UserCheck className="w-4 h-4" />
            Pending WhatsApp ({pendingClusters.length})
          </button>
          <button
            onClick={() => { setActiveTab('walkin'); setSuccessInfo(null); }}
            className={`px-4 py-2 rounded-lg transition flex items-center gap-1.5 ${activeTab === 'walkin' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <Plus className="w-4 h-4" />
            Fast Walk-in Registration
          </button>
          <button
            onClick={() => { setActiveTab('clusters'); setSuccessInfo(null); }}
            className={`px-4 py-2 rounded-lg transition flex items-center gap-1.5 ${activeTab === 'clusters' ? 'bg-white text-indigo-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
          >
            <Users className="w-4 h-4" />
            All Active Clusters & Bands
          </button>
        </div>
      </div>

      {actionError && (
        <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-xl text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
          <span>{actionError}</span>
        </div>
      )}

      {/* Success Modal / Banner when bands are issued */}
      {successInfo && (
        <div className="p-6 bg-emerald-50 border-2 border-emerald-400 rounded-2xl shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-emerald-900 font-bold text-base">
              <CheckCircle className="w-6 h-6 text-emerald-600" />
              Wristbands Successfully Issued to Family!
            </div>
            <button
              onClick={() => setSuccessInfo(null)}
              className="text-xs text-emerald-700 underline font-semibold"
            >
              Dismiss
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white p-4 rounded-xl border border-emerald-200">
              <div className="text-[11px] text-slate-500 uppercase font-bold">Family Cluster Code</div>
              <div className="text-xl font-black text-slate-900">{successInfo.clusterCode}</div>
            </div>

            {/* Secret Release PIN */}
            <div className="bg-white p-4 rounded-xl border-2 border-amber-300 relative overflow-hidden">
              <div className="text-[11px] text-amber-700 uppercase font-black flex items-center gap-1">
                <Key className="w-3.5 h-3.5" />
                Confidential Handover Release PIN
              </div>
              <div className="text-2xl font-black text-amber-900 tracking-widest">{successInfo.pin}</div>
              <p className="text-[10px] text-slate-500 mt-1">
                Tell the guardian: <em>"Keep this 6-digit PIN safe. Authorized helpdesk will ask for this PIN if a child needs to be verified for handover."</em>
              </p>
            </div>

            <div className="bg-white p-4 rounded-xl border border-emerald-200 flex flex-col justify-center">
              <div className="text-[11px] text-slate-500 uppercase font-bold">Wristbands Generated</div>
              <div className="text-xl font-black text-indigo-700">{successInfo.bands.length} Bands Linked</div>
            </div>
          </div>

          {/* Generated Bands Printing List */}
          <div className="space-y-2">
            <div className="text-xs font-bold text-slate-700">Print Issued Wristband Labels:</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {successInfo.bands.map((b) => (
                <div key={b.band_id} className="bg-white p-3 rounded-xl border border-slate-200 flex items-center justify-between shadow-2xs">
                  <div>
                    <div className="text-xs font-black text-slate-900">{b.band_id}</div>
                    <div className="text-[11px] text-slate-500">{b.assigned_member_name || 'Member'}</div>
                  </div>
                  <button
                    onClick={() => setSelectedBandForPrint(b.band_id)}
                    className="px-3 py-1.5 bg-slate-900 hover:bg-black text-white rounded-lg text-xs font-semibold flex items-center gap-1 transition"
                  >
                    <Printer className="w-3.5 h-3.5" />
                    Print Label
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 1: PENDING WHATSAPP PRE-REGISTRATIONS */}
      {activeTab === 'pending' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-base font-bold text-slate-900">Pending WhatsApp Pre-Registrations</h2>
              <p className="text-xs text-slate-500">
                Pilgrims who registered on WhatsApp and are arriving at the stall to verify their contact and collect physical wristbands.
              </p>
            </div>
            <button
              onClick={loadData}
              className="p-2 text-slate-500 hover:text-slate-900 bg-slate-50 rounded-lg border border-slate-200 transition"
              title="Refresh List"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          {pendingClusters.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-xs">
              No pending WhatsApp pre-registrations at this moment.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-slate-50 text-slate-500 border-b border-slate-200 font-bold uppercase tracking-wider">
                    <th className="p-3">Reference</th>
                    <th className="p-3">Guardian</th>
                    <th className="p-3">Primary Phone</th>
                    <th className="p-3">Backup Phone</th>
                    <th className="p-3">Bands Req.</th>
                    <th className="p-3">Dependents</th>
                    <th className="p-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {pendingClusters.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50 transition">
                      <td className="p-3 font-mono font-bold text-indigo-700">{c.registration_ref || c.cluster_code}</td>
                      <td className="p-3 font-semibold text-slate-900">{c.primary_guardian_name}</td>
                      <td className="p-3 text-slate-600 font-mono">{c.primary_phone}</td>
                      <td className="p-3 text-slate-500 font-mono">{c.backup_phone || 'None'}</td>
                      <td className="p-3 font-bold text-slate-800">{c.members_count}</td>
                      <td className="p-3 text-slate-600 max-w-xs truncate">
                        {c.members.map((m) => m.name || (m as any).notes).join(', ') || 'Family'}
                      </td>
                      <td className="p-3 text-right">
                        <button
                          onClick={() => handleClaimPending(c.registration_ref || c.cluster_code)}
                          disabled={loading}
                          className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-lg transition shadow-xs text-xs flex items-center gap-1.5 ml-auto"
                        >
                          <CheckCircle className="w-3.5 h-3.5" />
                          Verify & Issue Bands
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: FAST WALK-IN REGISTRATION FORM */}
      {activeTab === 'walkin' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 max-w-2xl mx-auto space-y-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">Fast Stall Assisted Registration (~15-Second Flow)</h2>
            <p className="text-xs text-slate-500">
              For families who arrive directly at the stall without using WhatsApp. Minimal friction, zero government ID required.
            </p>
          </div>

          <form onSubmit={handleWalkInSubmit} className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Primary Guardian Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Subba Rao"
                  value={guardianName}
                  onChange={(e) => setGuardianName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Primary Mobile Number *</label>
                <input
                  type="tel"
                  required
                  placeholder="e.g. 9848022338"
                  value={primaryPhone}
                  onChange={(e) => setPrimaryPhone(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Alternative / Backup Phone (Optional)</label>
                <input
                  type="tel"
                  placeholder="e.g. 9440188221"
                  value={backupPhone}
                  onChange={(e) => setBackupPhone(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Number of Wristbands Needed (1 - 6)</label>
                <select
                  value={bandsCount}
                  onChange={(e) => setBandsCount(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                >
                  {[1, 2, 3, 4, 5, 6].map((n) => (
                    <option key={n} value={n}>{n} Wristband{n > 1 ? 's' : ''}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="font-bold text-slate-700 block mb-1">
                Family Members / Dependents (Names & ages separated by semicolons)
              </label>
              <input
                type="text"
                placeholder="e.g. Chaitanya, age 8; Bhavani, age 68"
                value={memberDetails}
                onChange={(e) => setMemberDetails(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
              />
            </div>

            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-600 flex items-center gap-2 text-[11px]">
              <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>
                Verbal consent confirmed. Guardian acknowledges data is used solely for pushkaralu child safety operations.
              </span>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl transition shadow-xs text-xs flex items-center justify-center gap-2"
            >
              <CheckCircle className="w-4 h-4" />
              Create Family Cluster & Issue Wristbands
            </button>
          </form>
        </div>
      )}

      {/* TAB 3: ALL ACTIVE CLUSTERS & BANDS */}
      {activeTab === 'clusters' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-900">Active Family Clusters & Wristband Grid</h2>
              <p className="text-xs text-slate-500">Search clusters, view members, reprint QR labels, or update band status.</p>
            </div>
            <div className="flex gap-2 w-full sm:w-auto">
              <div className="relative flex-1 sm:w-64">
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search cluster, phone, guardian..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && loadData()}
                  className="w-full pl-9 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <button
                onClick={loadData}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition"
              >
                Search
              </button>
            </div>
          </div>

          <div className="space-y-4">
            {clusters.map((c) => (
              <div key={c.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3 text-xs">
                <div className="flex flex-wrap justify-between items-center gap-2 border-b border-slate-200 pb-2">
                  <div className="flex items-center gap-3">
                    <span className="font-mono font-black text-sm text-indigo-700">{c.cluster_code}</span>
                    <span className="font-bold text-slate-900">{c.primary_guardian_name}</span>
                    <span className="text-slate-500 font-mono flex items-center gap-1">
                      <Phone className="w-3 h-3" /> {c.primary_phone}
                    </span>
                    {c.backup_phone && (
                      <span className="text-slate-400 font-mono">Alt: {c.backup_phone}</span>
                    )}
                  </div>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${c.status === 'VERIFIED_ACTIVE' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                    {c.status}
                  </span>
                </div>

                {/* Bands under this cluster */}
                <div>
                  <div className="text-[11px] font-bold text-slate-500 mb-2 uppercase">Issued Wristbands:</div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                    {c.bands.map((b) => (
                      <div key={b.band_id} className="bg-white p-2.5 rounded-lg border border-slate-200 flex justify-between items-center">
                        <div>
                          <div className="font-mono font-bold text-slate-900">{b.band_id}</div>
                          <div className="text-[10px] text-slate-500">{b.assigned_member_name}</div>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <select
                            value={b.status}
                            onChange={(e) => handleUpdateBandStatus(b.band_id, e.target.value)}
                            className="text-[10px] border border-slate-300 rounded px-1.5 py-0.5 bg-slate-50"
                          >
                            <option value="ACTIVE">ACTIVE</option>
                            <option value="ISSUED">ISSUED</option>
                            <option value="LOST">LOST</option>
                            <option value="DAMAGED">DAMAGED</option>
                            <option value="REVOKED">REVOKED</option>
                          </select>
                          <button
                            onClick={() => setSelectedBandForPrint(b.band_id)}
                            title="Print Label"
                            className="p-1 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded"
                          >
                            <Printer className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Printable Label Modal */}
      {selectedBandForPrint && (
        <PrintLabelModal
          bandId={selectedBandForPrint}
          onClose={() => setSelectedBandForPrint(null)}
        />
      )}
    </div>
  );
};
