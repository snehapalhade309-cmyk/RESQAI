/**
 * RESQAI - Multilingual AI Emergency Assistant Controller
 * Real-time Grounded Emergency Guidance in English, Hindi (हिंदी), and Marathi (मराठी).
 */

let currentAssistantLang = 'en';

document.addEventListener('DOMContentLoaded', () => {
  initAssistantView();
});

function initAssistantView() {
  const btnSend = document.getElementById('chat-btn-send');
  const chatInput = document.getElementById('chat-user-input');

  // Language switcher buttons
  const langBtns = document.querySelectorAll('.lang-btn');
  langBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      langBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentAssistantLang = btn.getAttribute('data-lang') || 'en';
      
      const welcomeMsg = currentAssistantLang === 'hi' 
        ? "नमस्ते! मैं रेस्क्यू-एआई (ResQAI) आपातकालीन सहायक हूँ। मैं वास्तविक समय मौसम, एनडीएमए चेतावनियों और सुरक्षा उपायों में आपकी सहायता कर सकता हूँ।"
        : currentAssistantLang === 'mr'
        ? "नमस्कार! मी रेस्क्यू-एआई (ResQAI) आपत्कालीन सहाय्यक आहे. मी सद्य हवामान, NDMA इशारे आणि सुरक्षा सूचनांसंदर्भात मार्गदर्शन करू शकतो."
        : "Hello! I am the ResQAI Emergency AI Assistant. I provide real-time grounded disaster response protocols, live weather telemetry, and verified emergency guidance.";
      
      appendChatMessage('assistant', welcomeMsg);
    });
  });

  // Prompt suggestion chips
  const chips = document.querySelectorAll('.chip-btn');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const text = chip.textContent.trim();
      if (chatInput) {
        chatInput.value = text;
        sendChatMessage();
      }
    });
  });

  if (btnSend && chatInput) {
    btnSend.addEventListener('click', (e) => {
      e.preventDefault();
      sendChatMessage();
    });

    chatInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }
}

async function sendChatMessage() {
  const chatInput = document.getElementById('chat-user-input');
  if (!chatInput) return;

  const msg = chatInput.value.trim();
  if (!msg) return;

  chatInput.value = '';
  appendChatMessage('user', msg);

  // Append temporary thinking indicator
  const typingId = appendChatMessage('assistant', '<div style="display:flex; gap:4px; align-items:center;"><span>Thinking & checking active sensors</span><span style="animation: pulse 1s infinite;">...</span></div>');

  try {
    const lat = AppState?.selectedCoords?.lat || 18.5204;
    const lon = AppState?.selectedCoords?.lon || 73.8567;

    const res = await fetch('/api/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        language: currentAssistantLang,
        latitude: lat,
        longitude: lon
      })
    });

    const data = await res.json();
    const typingElem = document.getElementById(typingId);
    if (typingElem) typingElem.remove();

    if (res.ok && data.reply) {
      appendChatMessage('assistant', formatMarkdown(data.reply));
    } else {
      appendChatMessage('assistant', 'I encountered an error processing your query. Please call **112** directly for emergency help.');
    }

  } catch (err) {
    const typingElem = document.getElementById(typingId);
    if (typingElem) typingElem.remove();
    appendChatMessage('assistant', 'Network communication interrupted. In immediate danger, call **112** (Emergency) or **108** (Medical Ambulance).');
  }
}

function appendChatMessage(role, htmlContent) {
  const history = document.getElementById('chat-history-container');
  if (!history) return;

  const msgId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
  const isUser = role === 'user';

  const div = document.createElement('div');
  div.id = msgId;
  div.className = `chat-msg ${role}`;
  div.innerHTML = `
    <div class="chat-avatar">${isUser ? 'YOU' : 'AI'}</div>
    <div class="chat-bubble">${htmlContent}</div>
  `;

  history.appendChild(div);
  history.scrollTop = history.scrollHeight;
  return msgId;
}

function formatMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h3>$1</h3>')
    .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*)\*/gim, '<em>$1</em>')
    .replace(/^- (.*$)/gim, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}
