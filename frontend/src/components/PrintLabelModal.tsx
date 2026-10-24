import { useState, useEffect } from 'react';
import { X, Printer, ShieldCheck } from 'lucide-react';
import { apiRequest } from '../api/client';

interface LabelData {
  band_id: string;
  qr_image_data: string;
  festival: string;
  emergency_helpline: string;
  police_control: string;
  instructions: string;
  status: string;
}

interface Props {
  bandId: string;
  onClose: () => void;
}

export const PrintLabelModal: React.FC<Props> = ({ bandId, onClose }) => {
  const [labelData, setLabelData] = useState<LabelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchLabel = async () => {
      try {
        const data = await apiRequest<LabelData>(`/registration/bands/${bandId}/label`);
        setLabelData(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchLabel();
  }, [bandId]);

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200 overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-slate-900 text-white flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Printer className="w-5 h-5 text-amber-400" />
            <h3 className="font-bold text-sm tracking-wide">Wristband Thermal Label Print Preview</h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Safeguard Notice */}
        <div className="bg-amber-50 px-6 py-2.5 border-b border-amber-200 text-amber-900 text-xs flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>
            <strong>Safeguard Enforced:</strong> Public QR payload contains ONLY the random Band ID. No names or phone numbers are ever printed on the wristband.
          </span>
        </div>

        {/* Label Container (Print Target) */}
        <div className="p-6 flex flex-col items-center">
          {loading && <div className="text-sm text-slate-500 py-10">Generating secure label preview...</div>}
          {error && <div className="text-sm text-red-600 py-10">{error}</div>}

          {labelData && (
            <div
              id="printable-band-label"
              className="w-full max-w-sm border-2 border-black rounded-xl p-4 bg-white shadow-sm flex flex-col items-center text-center space-y-2 font-mono text-black print:border-none print:shadow-none"
            >
              <div className="text-xs font-black tracking-wider uppercase border-b-2 border-black w-full pb-1">
                GODAVARI PUSHKARALU 2027 • BANDHAM QR
              </div>

              {/* QR Code */}
              <div className="p-2 border border-slate-300 rounded bg-white">
                <img
                  src={labelData.qr_image_data}
                  alt={`QR for ${labelData.band_id}`}
                  className="w-40 h-40 object-contain mx-auto"
                />
              </div>

              {/* Random Band ID */}
              <div className="text-lg font-black tracking-widest bg-slate-100 px-3 py-0.5 rounded border border-slate-300">
                {labelData.band_id}
              </div>

              <div className="text-[11px] font-sans text-slate-700 leading-tight">
                {labelData.instructions}
              </div>

              <div className="w-full border-t border-dashed border-slate-400 pt-1 text-[10px] flex justify-between font-bold text-slate-800">
                <span>EMERGENCY: {labelData.emergency_helpline}</span>
                <span>POLICE: {labelData.police_control}</span>
              </div>
            </div>
          )}
        </div>

        {/* Modal Actions */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-100 transition"
          >
            Close
          </button>
          <button
            onClick={handlePrint}
            className="px-4 py-2 bg-slate-900 hover:bg-black text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow"
          >
            <Printer className="w-4 h-4" />
            Print Wristband Label
          </button>
        </div>
      </div>
    </div>
  );
};
