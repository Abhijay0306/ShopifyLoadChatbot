document.addEventListener('DOMContentLoaded', function() {
  const container = document.getElementById('ai-chat-bubble-container');
  if (!container) return;

  const toggleBtn = document.getElementById('ai-chat-toggle');
  const closeBtn = document.getElementById('ai-chat-close');
  const chatWindow = document.getElementById('ai-chat-window');
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send');
  const messagesContainer = document.getElementById('chat-messages');

  const API_URL = window.AI_CHAT_API_URL || 'http://localhost:8000/ask'; // Fallback for dev

  // Toggle Chat
  toggleBtn.addEventListener('click', () => {
    chatWindow.classList.toggle('hidden');
  });

  closeBtn.addEventListener('click', () => {
    chatWindow.classList.add('hidden');
  });

  // Send Message
  async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    // Add User Message
    addMessage(text, 'user');
    input.value = '';

    // Add Loading Indicator
    const loadingId = addMessage('Thinking...', 'system', true);

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          // Add auth headers if needed via App Proxy
        },
        body: JSON.stringify({ query: text })
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const data = await response.json();
      
      // Remove loading
      removeMessage(loadingId);
      
      // Add Bot Message
      let botText = data.answer;
      if (data.sources && data.sources.length > 0) {
        botText += `<div class="source-citation">Sources: ${data.sources.join(', ')}</div>`;
      }
      addMessage(botText, 'system');

    } catch (error) {
      console.error('Error:', error);
      removeMessage(loadingId);
      addMessage("I'm sorry, I encountered an error connecting to the knowledge base.", 'system');
    }
  }

  sendBtn.addEventListener('click', sendMessage);
  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  function addMessage(text, sender, isLoading = false) {
    const div = document.createElement('div');
    div.classList.add('message', sender);
    if (isLoading) div.id = 'loading-message-' + Date.now();
    div.innerHTML = text; // Using innerHTML to render sources HTML
    messagesContainer.appendChild(div);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    return div.id;
  }

  function removeMessage(id) {
    if (!id) return;
    const el = document.getElementById(id);
    if (el) el.remove();
  }
});
