import { useState } from 'react';
import {
  Smartphone, Users, LifeBuoy, QrCode, User,
  ChevronDown, Check
} from 'lucide-react';

interface Props {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  currentUserRole: string;
  onRoleChange: (role: string) => void;
}

export const Navbar: React.FC<Props> = ({
  currentTab,
  onSelectTab,
  currentUserRole,
  onRoleChange,
}) => {
  const [showRoleMenu, setShowRoleMenu] = useState(false);

  const roles = [
    { id: 'ADMIN', name: 'District Administrator', desc: 'Full System Access' },
    { id: 'REGISTRATION_OPERATOR', name: 'Registration Operator', desc: 'Cluster & Band Issuance' },
    { id: 'HELPDESK_STAFF', name: 'Helpdesk & Police Staff', desc: 'Child Cases & Handover' },
    { id: 'SANITATION_SUPERVISOR', name: 'Sanitation Supervisor', desc: 'Facility Cleanliness' },
  ];

  return (
    <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
        {/* Brand */}
        <div className="flex items-center gap-3 cursor-pointer" onClick={() => onSelectTab('whatsapp')}>
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center font-black text-white shadow-md">
            GP
          </div>
          <div>
            <div className="font-bold text-sm tracking-tight flex items-center gap-1.5">
              Bandham QR Grid
              <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded font-mono font-normal">
                Pushkaralu 2027
              </span>
            </div>
            <div className="text-[10px] text-slate-400">
              WhatsApp-First Family Safety & Operations Architecture
            </div>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <nav className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-xl text-xs font-semibold">
          <button
            onClick={() => onSelectTab('whatsapp')}
            className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${currentTab === 'whatsapp' ? 'bg-emerald-600 text-white shadow' : 'text-slate-300 hover:text-white'}`}
          >
            <Smartphone className="w-3.5 h-3.5" />
            1. Pilgrim WhatsApp
          </button>
          <button
            onClick={() => onSelectTab('registration')}
            className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${currentTab === 'registration' ? 'bg-indigo-600 text-white shadow' : 'text-slate-300 hover:text-white'}`}
          >
            <Users className="w-3.5 h-3.5" />
            2. Registration & Issuance
          </button>
          <button
            onClick={() => onSelectTab('helpdesk')}
            className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${currentTab === 'helpdesk' ? 'bg-red-600 text-white shadow' : 'text-slate-300 hover:text-white'}`}
          >
            <LifeBuoy className="w-3.5 h-3.5" />
            3. Helpdesk Command
          </button>
          <button
            onClick={() => onSelectTab('scan')}
            className={`px-3 py-1.5 rounded-lg transition flex items-center gap-1.5 ${currentTab === 'scan' ? 'bg-amber-600 text-white shadow' : 'text-slate-300 hover:text-white'}`}
          >
            <QrCode className="w-3.5 h-3.5" />
            Public QR Scan
          </button>
        </nav>

        {/* Staff Role Switcher */}
        <div className="relative">
          <button
            onClick={() => setShowRoleMenu(!showRoleMenu)}
            className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 px-3 py-1.5 rounded-xl border border-slate-700 text-xs transition"
          >
            <User className="w-3.5 h-3.5 text-slate-300" />
            <div className="text-left">
              <div className="font-bold text-[11px] text-white">
                {roles.find((r) => r.id === currentUserRole)?.name}
              </div>
              <div className="text-[9px] text-slate-400 font-mono">Role: {currentUserRole}</div>
            </div>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
          </button>

          {showRoleMenu && (
            <div className="absolute right-0 mt-2 w-64 bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl py-2 z-50 text-xs">
              <div className="px-3 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-800">
                Switch Operational Persona
              </div>
              {roles.map((r) => (
                <button
                  key={r.id}
                  onClick={() => {
                    onRoleChange(r.id);
                    setShowRoleMenu(false);
                  }}
                  className={`w-full px-3 py-2 text-left flex items-start justify-between hover:bg-slate-800 transition ${currentUserRole === r.id ? 'bg-slate-800/60 text-emerald-400' : 'text-slate-200'}`}
                >
                  <div>
                    <div className="font-semibold text-xs">{r.name}</div>
                    <div className="text-[10px] text-slate-400">{r.desc}</div>
                  </div>
                  {currentUserRole === r.id && <Check className="w-4 h-4 text-emerald-400 mt-0.5" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
