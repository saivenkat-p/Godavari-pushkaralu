import { useState, useEffect } from 'react';
import {
  ShieldAlert, MapPin, PhoneCall, CheckCircle2, AlertTriangle,
  Navigation, LifeBuoy, ArrowLeft, Send
} from 'lucide-react';
import { apiRequest } from '../api/client';

interface Props {
  bandId: string;
  onBackToApp?: () => void;
}

export const PublicScanPage: React.FC<Props> = ({ bandId, onBackToApp }) => {
  const [scanInfo, setScanInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Report state
  const [finderName, setFinderName] = useState('');
  const [finderPhone, setFinderPhone] = useState('');
  const [manualGhat, setManualGhat] = useState('Kotilingala Ghat (Helpdesk 1)');
  const [coords, setCoords] = useState<{ lat: number; lng: number; acc: number } | null>(null);
  const [locPermissionStatus, setLocPermissionStatus] = useState<'prompt' | 'granted' | 'denied'>('prompt');
  const [submitting, setSubmitting] = useState(false);
  const [reportSuccess, setReportSuccess] = useState<any>(null);

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const data = await apiRequest(`/scan/${bandId}`);
        setScanInfo(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchInfo();
  }, [bandId]);

  const requestGpsLocation = () => {
    if (!navigator.geolocation) {
      setLocPermissionStatus('denied');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          acc: pos.coords.accuracy,
        });
        setLocPermissionStatus('granted');
      },
      () => {
        setLocPermissionStatus('denied');
      },
      { timeout: 8000 }
    );
  };

  const handleSubmitFoundReport = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const res = await apiRequest(`/scan/${bandId}/report-found`, {
        method: 'POST',
        body: JSON.stringify({
          band_id: bandId,
          finder_name: finderName || undefined,
          finder_contact: finderPhone || undefined,
          location_name: manualGhat,
          latitude: coords?.lat,
          longitude: coords?.lng,
          accuracy: coords?.acc,
          location_type: coords ? 'GPS' : 'MANUAL',
        }),
      });
      setReportSuccess(res);
    } catch (err: any) {
      alert(`Report failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col items-center p-4">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-xl border border-slate-200 overflow-hidden my-4 space-y-5 pb-8">
        {/* Top Header */}
        <div className="bg-[#075e54] text-white p-5 text-center relative">
          {onBackToApp && (
            <button
              onClick={onBackToApp}
              className="absolute left-4 top-5 text-emerald-200 hover:text-white flex items-center gap-1 text-xs"
            >
              <ArrowLeft className="w-4 h-4" /> Exit
            </button>
          )}
          <div className="inline-block px-3 py-0.5 rounded-full bg-emerald-800 text-emerald-200 text-[10px] font-bold tracking-wider uppercase mb-1">
            Godavari Pushkaralu 2027
          </div>
          <h1 className="text-xl font-black tracking-tight">Bandham QR Safety Grid</h1>
          <div className="text-xs text-emerald-100 mt-1 font-mono">
            Band Reference: <strong>{bandId}</strong>
          </div>
        </div>

        {loading && <div className="p-8 text-center text-xs text-slate-500">Checking band status...</div>}
        {error && (
          <div className="p-6 text-center space-y-3">
            <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto" />
            <div className="text-sm font-bold text-slate-800">{error}</div>
            <p className="text-xs text-slate-500">
              Please escort the child directly to the nearest Pushkaralu Police Booth or Call 1800-425-2027.
            </p>
          </div>
        )}

        {scanInfo && !reportSuccess && (
          <div className="p-5 space-y-5 text-xs">
            {/* Compassionate Safe Instruction Banner */}
            <div className="bg-amber-50 border-2 border-amber-300 rounded-2xl p-4 space-y-2">
              <div className="flex items-center gap-2 text-amber-900 font-bold text-sm">
                <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0" />
                Child Safeguarding Instructions
              </div>
              <ul className="space-y-1.5 text-slate-700 text-[11px] list-disc list-inside">
                <li>Please stay calm and keep the child safe and in sight.</li>
                <li><strong>NEVER hand the child to an unverified member of the public.</strong></li>
                <li>Bring the child to the nearest Helpdesk stall or uniformed Police officer.</li>
                <li>Submit your location below to instantly alert the family and operations team.</li>
              </ul>
            </div>

            {/* Found Child Report Form */}
            <form onSubmit={handleSubmitFoundReport} className="space-y-3 bg-slate-50 p-4 rounded-2xl border border-slate-200">
              <div className="font-bold text-slate-900 text-xs flex items-center gap-1.5">
                <MapPin className="w-4 h-4 text-emerald-600" />
                I Have Found This Child — Send Location Alert
              </div>

              {/* Location Fix Selector */}
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="font-semibold text-slate-700">Where are you at the Ghats?</label>
                  {locPermissionStatus !== 'granted' ? (
                    <button
                      type="button"
                      onClick={requestGpsLocation}
                      className="text-emerald-700 hover:text-emerald-800 font-bold text-[10px] flex items-center gap-0.5"
                    >
                      <Navigation className="w-3 h-3" /> Use My GPS
                    </button>
                  ) : (
                    <span className="text-emerald-600 font-bold text-[10px] flex items-center gap-0.5">
                      <CheckCircle2 className="w-3 h-3" /> GPS Acquired
                    </span>
                  )}
                </div>

                <select
                  value={manualGhat}
                  onChange={(e) => setManualGhat(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl bg-white text-xs outline-none"
                >
                  <option value="Kotilingala Ghat (Helpdesk Booth 1)">Kotilingala Ghat (Helpdesk Booth 1)</option>
                  <option value="Pushkar Ghat Main Steps (Helpdesk 2)">Pushkar Ghat Main Steps (Helpdesk 2)</option>
                  <option value="Saraswati Ghat Bathing Enclosure">Saraswati Ghat Bathing Enclosure</option>
                  <option value="Markandeya Ghat Temple Side">Markandeya Ghat Temple Side</option>
                  <option value="Goshpada Kshetram Ghat (Kovvur)">Goshpada Kshetram Ghat (Kovvur)</option>
                  <option value="Rajahmundry Railway Station Approach">Rajahmundry Railway Station Approach</option>
                </select>
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Your Name (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Ramesh"
                  value={finderName}
                  onChange={(e) => setFinderName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl bg-white text-xs outline-none"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Your Contact Number (Optional)</label>
                <input
                  type="tel"
                  placeholder="e.g. 9848011223"
                  value={finderPhone}
                  onChange={(e) => setFinderPhone(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-xl bg-white text-xs outline-none"
                />
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-3 bg-emerald-700 hover:bg-emerald-800 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2 transition shadow-md"
              >
                <Send className="w-4 h-4" />
                Submit Alert to Verified Guardian & Helpdesk
              </button>
            </form>

            {/* Direct Helpline Buttons */}
            <div className="space-y-2 pt-2">
              <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wide text-center">
                Emergency Immediate Contacts
              </div>
              <div className="grid grid-cols-2 gap-2">
                <a
                  href="tel:18004252027"
                  className="p-3 bg-emerald-50 hover:bg-emerald-100 text-emerald-900 border border-emerald-200 rounded-xl flex items-center justify-center gap-1.5 font-bold text-xs transition"
                >
                  <PhoneCall className="w-4 h-4 text-emerald-600" />
                  1800-425-2027
                </a>
                <a
                  href="tel:112"
                  className="p-3 bg-red-50 hover:bg-red-100 text-red-900 border border-red-200 rounded-xl flex items-center justify-center gap-1.5 font-bold text-xs transition"
                >
                  <LifeBuoy className="w-4 h-4 text-red-600" />
                  Police (112)
                </a>
              </div>
            </div>
          </div>
        )}

        {reportSuccess && (
          <div className="p-6 text-center space-y-4">
            <div className="w-14 h-14 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <div className="space-y-1">
              <h2 className="text-base font-bold text-slate-900">Guardian Alert Dispatched!</h2>
              <div className="text-xs font-mono text-indigo-700 font-bold">
                Case Reference: {reportSuccess.case_number}
              </div>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              {reportSuccess.instructions}
            </p>
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-[11px] text-slate-500">
              Our zonal helpdesk team at <strong>{manualGhat}</strong> has been notified.
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
