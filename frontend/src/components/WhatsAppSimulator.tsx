import { useState, useEffect, useRef } from 'react';
import { Send, RotateCcw, Smartphone, CheckCheck, ShieldCheck, Languages, Sparkles } from 'lucide-react';
import { apiRequest } from '../api/client';

interface Message {
  sender: 'user' | 'bot';
  text: string;
  time: string;
}

export const WhatsAppSimulator: React.FC = () => {
  const [phoneNumber, setPhoneNumber] = useState('919876543210');
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionLang, setSessionLang] = useState('te');
  const [currentState, setCurrentState] = useState('MAIN_MENU');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isSendingRef = useRef<boolean>(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initial greeting on mount
  useEffect(() => {
    handleSendMessage('నమస్కారం');
  }, []);

  const handleSendMessage = async (textToSend?: string) => {
    if (isSendingRef.current || loading) return;
    const text = (textToSend !== undefined ? textToSend : inputText).trim();
    if (!text) return;

    isSendingRef.current = true;
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsg: Message = { sender: 'user', text, time: timeStr };
    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setLoading(true);

    try {
      const res = await apiRequest<{ replies: string[]; session_language: string; current_state: string }>(
        '/simulator/chat',
        {
          method: 'POST',
          body: JSON.stringify({
            phone_number: phoneNumber,
            message_text: text,
          }),
        }
      );

      setSessionLang(res.session_language);
      setCurrentState(res.current_state);

      const botMessages: Message[] = res.replies.map((r) => ({
        sender: 'bot',
        text: r,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }));

      setMessages((prev) => [...prev, ...botMessages]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: `⚠️ Error communicating with assistant: ${err.message}`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setLoading(false);
      isSendingRef.current = false;
    }
  };

  const handleReset = async () => {
    try {
      await apiRequest(`/simulator/reset?phone_number=${phoneNumber}`, { method: 'POST' });
      setMessages([]);
      handleSendMessage('0');
    } catch (err) {
      console.error(err);
    }
  };

  const formatWhatsAppText = (text: string) => {
    // Basic formatting for bold (*text*), italics (_text_)
    return text.split('\n').map((line, idx) => {
      let formatted = line;
      // Bold
      formatted = formatted.replace(/\*([^*]+)\*/g, '<strong>$1</strong>');
      // Italic
      formatted = formatted.replace(/_([^_]+)_/g, '<em>$1</em>');
      return (
        <span
          key={idx}
          className="block min-h-[1.2rem]"
          dangerouslySetInnerHTML={{ __html: formatted }}
        />
      );
    });
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 p-4 max-w-6xl mx-auto items-start">
      {/* Simulator Guidance Sidebar */}
      <div className="w-full lg:w-1/3 bg-white rounded-2xl shadow-sm border border-slate-200 p-5 space-y-4">
        <div className="flex items-center gap-2 text-emerald-700">
          <Smartphone className="w-6 h-6" />
          <h2 className="text-xl font-bold">Pilgrim WhatsApp Assistant</h2>
        </div>
        <p className="text-xs text-slate-600 leading-relaxed">
          This is the primary citizen interface. Pilgrims do not install a mobile app. 
          They interact directly through WhatsApp in <strong>Telugu, English, or Hindi</strong>.
        </p>

        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl space-y-1 text-xs">
          <div className="font-semibold text-emerald-900 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            Meta WhatsApp Cloud API Adapter Active
          </div>
          <div className="text-emerald-700">
            Currently running in <strong>Local Simulation Mode</strong>. Real WhatsApp Webhook verification and Graph API dispatcher are fully wired and test-ready.
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-700">Simulated Pilgrim Phone Number:</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              className="flex-1 px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 outline-none"
            />
            <button
              onClick={handleReset}
              title="Reset Conversation Session"
              className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium flex items-center gap-1 transition"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset
            </button>
          </div>
        </div>

        {/* Quick Test Shortcuts */}
        <div className="space-y-2 pt-2 border-t border-slate-100">
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            Quick Test Prompts
          </div>
          <div className="grid grid-cols-1 gap-1.5 text-xs">
            <button
              disabled={loading}
              onClick={() => handleSendMessage('1')}
              className="text-left px-3 py-2 bg-slate-50 hover:bg-emerald-50 border border-slate-200 hover:border-emerald-300 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              1️⃣ <strong>Family Bandham QR Registration</strong> (Guided flow)
            </button>
            <button
              disabled={loading}
              onClick={() => handleSendMessage('2')}
              className="text-left px-3 py-2 bg-slate-50 hover:bg-red-50 border border-slate-200 hover:border-red-300 rounded-lg transition text-red-900 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              2️⃣ <strong>Report Missing Child</strong> (PA Script + BOLO)
            </button>
            <button
              disabled={loading}
              onClick={() => handleSendMessage('3')}
              className="text-left px-3 py-2 bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-300 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              3️⃣ <strong>I Found a Lost Child</strong> (Safety instructions)
            </button>
            <button
              disabled={loading}
              onClick={() => handleSendMessage('4')}
              className="text-left px-3 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              4️⃣ <strong>Ghats & Facilities</strong> (Locations & Medical)
            </button>
            <button
              disabled={loading}
              onClick={() => handleSendMessage('5')}
              className="text-left px-3 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              5️⃣ <strong>Cleanliness & Toilet Report</strong> (Dispatch ticket)
            </button>
            <button
              disabled={loading}
              onClick={() => handleSendMessage('6')}
              className="text-left px-3 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              6️⃣ <strong>Official Approved Rates</strong> (Tariffs)
            </button>
            <button
              disabled={loading}
              onClick={() => handleSendMessage('7')}
              className="text-left px-3 py-2 bg-slate-50 hover:bg-amber-50 border border-slate-200 hover:border-amber-300 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              7️⃣ <strong>Report Overcharging / Scam</strong>
            </button>
            <button
              disabled={loading}
              onClick={() => handleSendMessage('8')}
              className="text-left px-3 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              8️⃣ <strong>Emergency Police / 1800 Helpline</strong>
            </button>
          </div>
        </div>

        {/* Language Quick Switcher */}
        <div className="pt-2 border-t border-slate-100">
          <label className="text-xs font-semibold text-slate-600 block mb-1 flex items-center gap-1">
            <Languages className="w-3.5 h-3.5" /> Language Switcher:
          </label>
          <div className="grid grid-cols-3 gap-1.5 text-xs">
            <button
              disabled={loading}
              onClick={() => handleSendMessage('తెలుగు')}
              className={`py-1 px-2 rounded border font-medium transition disabled:opacity-50 ${sessionLang === 'te' ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-slate-50 text-slate-700 border-slate-200'}`}
            >
              తెలుగు
            </button>
            <button
              disabled={loading}
              onClick={() => handleSendMessage('English')}
              className={`py-1 px-2 rounded border font-medium transition disabled:opacity-50 ${sessionLang === 'en' ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-slate-50 text-slate-700 border-slate-200'}`}
            >
              English
            </button>
            <button
              disabled={loading}
              onClick={() => handleSendMessage('हिन्दी')}
              className={`py-1 px-2 rounded border font-medium transition disabled:opacity-50 ${sessionLang === 'hi' ? 'bg-emerald-600 text-white border-emerald-600' : 'bg-slate-50 text-slate-700 border-slate-200'}`}
            >
              हिन्दी
            </button>
          </div>
        </div>
      </div>

      {/* Realistic Mobile Device Container */}
      <div className="w-full lg:w-2/3 max-w-md mx-auto bg-slate-900 rounded-[2.5rem] p-3 shadow-2xl border-4 border-slate-800">
        <div className="bg-[#efeae2] rounded-[2rem] overflow-hidden flex flex-col h-[700px] relative">
          {/* WhatsApp Header */}
          <div className="bg-[#075e54] text-white px-4 py-3 flex items-center justify-between shadow-md z-10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-emerald-700 flex items-center justify-center font-bold text-white border-2 border-emerald-400">
                GP
              </div>
              <div>
                <div className="font-semibold text-sm flex items-center gap-1.5">
                  Bandham Assistant 2027
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-300" />
                </div>
                <div className="text-[11px] text-emerald-200">
                  [PILOT PROTOTYPE] Godavari Pushkaralu • Online
                </div>
              </div>
            </div>
            <button
              onClick={handleReset}
              className="text-xs bg-emerald-800 hover:bg-emerald-700 text-emerald-100 px-2 py-1 rounded transition"
            >
              Clear
            </button>
          </div>

          {/* Sub-header status strip */}
          <div className="bg-[#128c7e] text-emerald-100 text-[10px] px-3 py-1 flex justify-between items-center">
            <span>State: <strong>{currentState}</strong></span>
            <span>Lang: <strong>{sessionLang.toUpperCase()}</strong></span>
            <span>24x7 Emergency Grid</span>
          </div>

          {/* Chat Messages Body */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2.5 bg-[#efeae2]">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-xs shadow-sm relative leading-relaxed ${
                    msg.sender === 'user'
                      ? 'bg-[#d9fdd3] text-slate-800 rounded-br-none'
                      : 'bg-white text-slate-900 rounded-bl-none border border-slate-100'
                  }`}
                >
                  <div className="whitespace-pre-wrap">{formatWhatsAppText(msg.text)}</div>
                  <div className="text-[9px] text-slate-400 text-right mt-1 flex items-center justify-end gap-1">
                    {msg.time}
                    {msg.sender === 'user' && <CheckCheck className="w-3 h-3 text-sky-500" />}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white rounded-2xl px-4 py-2 text-xs shadow-sm border border-slate-100 flex items-center gap-1 text-slate-500">
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" />
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce delay-100" />
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce delay-200" />
                  <span className="ml-1 text-[11px]">Assistant typing...</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Footer */}
          <div className="p-2.5 bg-[#f0f2f5] border-t border-slate-200 flex items-center gap-2">
            <input
              type="text"
              placeholder="Type a message or menu number (e.g., 1)..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
              className="flex-1 bg-white border border-slate-300 rounded-full px-4 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={loading || !inputText.trim()}
              className="p-2 bg-[#075e54] hover:bg-[#128c7e] text-white rounded-full transition disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
