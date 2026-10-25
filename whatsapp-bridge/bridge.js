import makeWASocket, {
    DisconnectReason,
    useMultiFileAuthState,
    fetchLatestBaileysVersion
} from '@whiskeysockets/baileys';
import qrcodeTerminal from 'qrcode-terminal';
import QRCode from 'qrcode';
import http from 'http';
import pino from 'pino';

const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8003/api/simulator/chat';
const PORT = process.env.BRIDGE_PORT || 3333;

let currentQR = null;
let connectionStatus = 'INITIALIZING';
let linkedPhoneNumber = null;
let globalSock = null;
const sentByBotMessageIds = new Set();

// Lightweight HTTP server
const server = http.createServer(async (req, res) => {
    // API endpoint to trigger outbound WhatsApp messages
    if (req.url === '/send' && req.method === 'POST') {
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', async () => {
            try {
                const data = JSON.parse(body);
                const to = String(data.to || '').replace('+', '').replace('@s.whatsapp.net', '').trim();
                const jid = `${to}@s.whatsapp.net`;
                const text = data.text;
                if (globalSock && connectionStatus === 'CONNECTED') {
                    const sent = await globalSock.sendMessage(jid, { text });
                    if (sent?.key?.id) sentByBotMessageIds.add(sent.key.id);
                    res.writeHead(200, { 'Content-Type': 'application/json' });
                    return res.end(JSON.stringify({ status: 'SENT', to, id: sent?.key?.id }));
                } else {
                    res.writeHead(503, { 'Content-Type': 'application/json' });
                    return res.end(JSON.stringify({ status: 'NOT_CONNECTED', connectionStatus }));
                }
            } catch (err) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                return res.end(JSON.stringify({ status: 'ERROR', error: err.message }));
            }
        });
        return;
    }

    if (req.url === '/qr.png' && currentQR) {
        res.writeHead(200, { 'Content-Type': 'image/png' });
        const png = await QRCode.toBuffer(currentQR, { width: 350 });
        return res.end(png);
    }

    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    if (connectionStatus === 'CONNECTED') {
        return res.end(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Bandham QR WhatsApp Bridge</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #0b141a; color: #e9edef; text-align: center; }
                    .card { background: #111b21; padding: 40px; border-radius: 16px; border: 1px solid #222e35; max-width: 480px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
                    .badge { display: inline-block; background: #00a884; color: #fff; font-weight: bold; padding: 6px 14px; border-radius: 20px; font-size: 14px; margin-bottom: 20px; }
                    h1 { margin: 0 0 10px 0; font-size: 24px; color: #25d366; }
                    p { color: #8696a0; line-height: 1.5; }
                    .phone { color: #53bdeb; font-size: 18px; font-weight: bold; }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="badge">● CONNECTED & ACTIVE</div>
                    <h1>WhatsApp Bot is Online!</h1>
                    <p class="phone">+${linkedPhoneNumber || 'Authorized Device'}</p>
                    <p>You can now send any message (like <strong>'నమస్కారం'</strong> or <strong>'Hi'</strong>) in WhatsApp, and the Godavari Pushkaralu Bandham assistant will reply live!</p>
                </div>
            </body>
            </html>
        `);
    }

    if (currentQR) {
        return res.end(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Scan WhatsApp QR Code</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <meta http-equiv="refresh" content="15">
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #0b141a; color: #e9edef; text-align: center; }
                    .card { background: #111b21; padding: 32px; border-radius: 16px; border: 1px solid #222e35; max-width: 460px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
                    h1 { margin: 0 0 8px 0; font-size: 22px; color: #e9edef; }
                    p { color: #8696a0; font-size: 14px; line-height: 1.4; margin-bottom: 20px; }
                    .qr-box { background: #ffffff; padding: 16px; border-radius: 12px; display: inline-block; margin-bottom: 16px; }
                    ol { text-align: left; color: #8696a0; font-size: 13px; padding-left: 20px; }
                    li { margin-bottom: 6px; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Link Your WhatsApp</h1>
                    <p>Scan this QR code with WhatsApp to connect the Godavari Pushkaralu Bot directly to your phone.</p>
                    <div class="qr-box">
                        <img src="/qr.png" width="300" height="300" alt="WhatsApp QR Code" />
                    </div>
                    <ol>
                        <li>Open WhatsApp on your phone</li>
                        <li>Tap <strong>Menu (⋮)</strong> or <strong>Settings</strong> ➔ <strong>Linked Devices</strong></li>
                        <li>Tap <strong>Link a Device</strong> and point your camera at this QR code</li>
                    </ol>
                </div>
            </body>
            </html>
        `);
    }

    return res.end(`
        <!DOCTYPE html>
        <html>
        <head><meta http-equiv="refresh" content="2"></head>
        <body style="background:#0b141a;color:#fff;font-family:sans-serif;text-align:center;padding:50px;">
            <h2>Connecting to WhatsApp...</h2>
            <p>Please wait a moment...</p>
        </body>
        </html>
    `);
});

server.listen(PORT, () => {
    console.log(`🌐 WhatsApp Bridge Web UI running on http://localhost:${PORT}`);
});

async function startBridge() {
    const { state, saveCreds } = await useMultiFileAuthState('./auth_info_baileys');
    const { version } = await fetchLatestBaileysVersion();

    const sock = makeWASocket({
        version,
        logger: pino({ level: 'silent' }),
        auth: state,
        printQRInTerminal: false
    });

    globalSock = sock;

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            currentQR = qr;
            connectionStatus = 'WAITING_FOR_SCAN';
            console.log('\n======================================================');
            console.log('📲 SCAN THIS QR CODE IN WHATSAPP (OR OPEN http://localhost:3333):');
            console.log('======================================================\n');
            qrcodeTerminal.generate(qr, { small: true });
            console.log('\n👉 Or open in browser: http://localhost:3333\n');
        }

        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect?.error)?.output?.statusCode !== DisconnectReason.loggedOut;
            console.log('⚠️ Connection closed due to:', lastDisconnect?.error, ', reconnecting:', shouldReconnect);
            connectionStatus = 'DISCONNECTED';
            currentQR = null;
            if (shouldReconnect) {
                setTimeout(startBridge, 3000);
            }
        } else if (connection === 'open') {
            console.log('\n🎉 ======================================================');
            console.log('✅ WHATSAPP CONNECTED SUCCESSFULLY!');
            console.log(`📱 User: ${sock.user?.id || 'Connected'}`);
            console.log('🤖 Bandham QR Bot is now listening for incoming messages!');
            console.log('======================================================\n');
            connectionStatus = 'CONNECTED';
            currentQR = null;
            linkedPhoneNumber = sock.user?.id ? sock.user.id.split(':')[0] : 'Linked';
        }
    });

    sock.ev.on('messages.upsert', async (m) => {
        if (m.type !== 'notify') return;

        for (const msg of m.messages) {
            const msgId = msg.key.id;
            // Ignore messages sent by our bot
            if (sentByBotMessageIds.has(msgId)) continue;

            const remoteJid = msg.key.remoteJid;
            if (!remoteJid || remoteJid.includes('@g.us') || remoteJid.includes('broadcast')) continue;

            // If it's fromMe but remoteJid is self, allow self-testing!
            const myJid = sock.user?.id ? sock.user.id.split(':')[0] : '';
            const isSelfChat = remoteJid.includes(myJid);
            if (msg.key.fromMe && !isSelfChat) continue;

            const text = msg.message?.conversation ||
                         msg.message?.extendedTextMessage?.text ||
                         msg.message?.imageMessage?.caption ||
                         '';

            if (!text.trim()) continue;

            const senderPhone = remoteJid.split('@')[0];
            console.log(`📩 Inbound WhatsApp from +${senderPhone}: "${text}"`);

            try {
                // Forward message to Bandham FastAPI Backend
                const response = await fetch(BACKEND_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        phone_number: senderPhone,
                        message_text: text
                    })
                });

                if (!response.ok) {
                    console.error('Backend returned error status:', response.status);
                    continue;
                }

                const data = await response.json();
                const replies = data.replies || [];

                for (const reply of replies) {
                    console.log(`📤 Outbound WhatsApp reply to +${senderPhone}: "${reply.slice(0, 50)}..."`);
                    const sent = await sock.sendMessage(remoteJid, { text: reply });
                    if (sent?.key?.id) {
                        sentByBotMessageIds.add(sent.key.id);
                        if (sentByBotMessageIds.size > 2000) sentByBotMessageIds.clear();
                    }
                }
            } catch (err) {
                console.error('Error forwarding message to backend:', err.message);
            }
        }
    });
}

startBridge();
