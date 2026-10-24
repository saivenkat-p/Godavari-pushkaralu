import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { WhatsAppSimulator } from './components/WhatsAppSimulator';
import { RegistrationDashboard } from './components/RegistrationDashboard';
import { HelpdeskDashboard } from './components/HelpdeskDashboard';
import { PublicScanPage } from './components/PublicScanPage';
import { setAuthToken, apiRequest } from './api/client';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<string>('whatsapp');
  const [currentUserRole, setCurrentUserRole] = useState<string>('ADMIN');
  const [scannedBandId, setScannedBandId] = useState<string>('BND-8F32A1C9');

  // Check URL pathname for direct /scan/:bandId support
  useEffect(() => {
    const path = window.location.pathname;
    if (path.startsWith('/scan/')) {
      const bId = path.replace('/scan/', '');
      if (bId) {
        setScannedBandId(bId);
        setCurrentTab('scan');
      }
    }
  }, []);

  // Sync auth token based on selected role
  useEffect(() => {
    const loginForRole = async () => {
      const credentialsMap: Record<string, { u: string; p: string }> = {
        ADMIN: { u: 'admin', p: 'Admin@2027' },
        REGISTRATION_OPERATOR: { u: 'reg_operator', p: 'Register@2027' },
        HELPDESK_STAFF: { u: 'helpdesk_operator', p: 'Helpdesk@2027' },
        SANITATION_SUPERVISOR: { u: 'sanitation_lead', p: 'Sanitation@2027' },
      };

      const cred = credentialsMap[currentUserRole];
      if (cred) {
        try {
          const res = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username: cred.u, password: cred.p }),
          });
          setAuthToken(res.access_token);
        } catch (err) {
          console.error('Role auto-login error:', err);
        }
      }
    };

    loginForRole();
  }, [currentUserRole]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <Navbar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        currentUserRole={currentUserRole}
        onRoleChange={setCurrentUserRole}
      />

      <main className="flex-1">
        {currentTab === 'whatsapp' && <WhatsAppSimulator />}
        {currentTab === 'registration' && <RegistrationDashboard />}
        {currentTab === 'helpdesk' && <HelpdeskDashboard />}
        {currentTab === 'scan' && (
          <PublicScanPage
            bandId={scannedBandId}
            onBackToApp={() => setCurrentTab('whatsapp')}
          />
        )}
      </main>

      <footer className="bg-slate-900 text-slate-400 border-t border-slate-800 text-[11px] py-4 text-center">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row justify-between items-center gap-2">
          <div>
            <strong>Godavari Pushkaralu 2027</strong> • Bandham QR Zero-App Pilgrim Safety Grid
          </div>
          <div>
            AP Innovation Society & RTIH AP Proposal Reference • Telugu, Hindi & English Multilingual WhatsApp Architecture
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
