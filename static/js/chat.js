document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    const chatMessages = document.getElementById('chatMessages');
    const preferencesForm = document.getElementById('preferencesForm');

    // Generate a simple user ID for demo purposes
    const userId = 'user_' + Math.random().toString(36).substr(2, 9);

    function addMessage(content, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'system'}`;
        messageDiv.textContent = content;
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showLoading() {
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message system loading-message';
        loadingDiv.innerHTML = '<div class="loading"></div>';
        chatMessages.appendChild(loadingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return loadingDiv;
    }

    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const message = messageInput.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessage(message, true);
        messageInput.value = '';

        // Show loading indicator
        const loadingMessage = showLoading();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    user_id: userId
                })
            });

            const data = await response.json();
            
            // Remove loading indicator
            loadingMessage.remove();

            if (data.status === 'success') {
                addMessage(data.response);
            } else {
                addMessage('Sorry, there was an error processing your request.');
            }
        } catch (error) {
            loadingMessage.remove();
            addMessage('Sorry, there was an error connecting to the server.');
        }
    });

    preferencesForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const preferences = {
            budget: document.getElementById('budget').value,
            travelStyle: document.getElementById('travelStyle').value
        };

        try {
            const response = await fetch('/api/preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: userId,
                    preferences: preferences
                })
            });

            const data = await response.json();
            
            if (data.status === 'success') {
                addMessage('Preferences updated successfully! How can I help you plan your trip?');
            } else {
                addMessage('Sorry, there was an error saving your preferences.');
            }
        } catch (error) {
            addMessage('Sorry, there was an error connecting to the server.');
        }
    });
});
