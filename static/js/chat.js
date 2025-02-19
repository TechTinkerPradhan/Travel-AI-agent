document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    const chatMessages = document.getElementById('chatMessages');
    const preferencesForm = document.getElementById('preferencesForm');
    const submitButton = chatForm.querySelector('button[type="submit"]');
    const calendarStatus = document.getElementById('calendarStatus');
    const calendarAuthBtn = document.getElementById('calendarAuthBtn');

    // Generate a simple user ID for demo purposes
    const userId = 'user_' + Math.random().toString(36).substr(2, 9);

    async function createCalendarEvent(eventDetails) {
        try {
            const response = await fetch('/api/calendar/event', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(eventDetails)
            });

            const data = await response.json();
            if (data.status === 'success') {
                addMessage('Successfully added event to your Google Calendar!');
            } else {
                addMessage('Failed to add event to calendar: ' + data.message, false, true);
            }
        } catch (error) {
            addMessage('Error creating calendar event: ' + error.message, false, true);
        }
    }

    function createResponseOption(optionData, query) {
        console.log('Creating response option:', optionData);
        const optionDiv = document.createElement('div');
        optionDiv.className = 'message system response-option';

        // Ensure the content is properly sanitized and formatted
        try {
            optionDiv.innerHTML = marked.parse(optionData.content);
        } catch (e) {
            console.error('Error parsing markdown:', e);
            optionDiv.textContent = optionData.content;
        }

        const selectButton = document.createElement('button');
        selectButton.className = 'btn btn-sm btn-outline-primary mt-2 select-response-btn';
        selectButton.innerHTML = '<i data-feather="check"></i> Select this option';

        // Add calendar button if the response contains itinerary-related content
        const content = optionData.content.toLowerCase();
        if (content.includes('itinerary') || content.includes('schedule')) {
            const calendarButton = document.createElement('button');
            calendarButton.className = 'btn btn-sm btn-outline-secondary mt-2 ms-2';
            calendarButton.innerHTML = '<i data-feather="calendar"></i> Add to Calendar';

            calendarButton.addEventListener('click', async () => {
                const eventDetails = {
                    summary: 'Travel Itinerary',
                    description: optionData.content,
                    start: {
                        dateTime: new Date().toISOString(),
                        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
                    },
                    end: {
                        dateTime: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
                        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
                    }
                };
                await createCalendarEvent(eventDetails);
            });

            const buttonGroup = document.createElement('div');
            buttonGroup.className = 'd-flex gap-2 mt-2';
            buttonGroup.appendChild(selectButton);
            buttonGroup.appendChild(calendarButton);
            optionDiv.appendChild(buttonGroup);
        } else {
            optionDiv.appendChild(selectButton);
        }

        selectButton.addEventListener('click', async () => {
            try {
                console.log('Selecting response:', optionData);
                const response = await fetch('/api/chat/select', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        user_id: userId,
                        original_query: query,
                        selected_response: optionData.content
                    })
                });

                const data = await response.json();
                if (data.status === 'success') {
                    // Hide other options
                    const options = chatMessages.querySelectorAll('.response-option');
                    options.forEach(option => {
                        if (option !== optionDiv) {
                            option.style.display = 'none';
                        }
                    });

                    // Update selected option appearance
                    selectButton.disabled = true;
                    selectButton.innerHTML = '<i data-feather="check-circle"></i> Selected';
                    feather.replace();

                    // Add preference analysis if available
                    if (data.preference_analysis) {
                        const analysisDiv = document.createElement('div');
                        analysisDiv.className = 'message system preference-analysis mt-2';
                        analysisDiv.innerHTML = `
                            <small class="text-muted">Preferences identified:</small>
                            <pre>${JSON.stringify(JSON.parse(data.preference_analysis), null, 2)}</pre>
                        `;
                        chatMessages.appendChild(analysisDiv);
                    }
                }
            } catch (error) {
                console.error('Error selecting response:', error);
                addMessage('Error processing your selection. Please try again.', false, true);
            }
        });

        feather.replace();
        return optionDiv;
    }

    function addMessage(content, isUser = false, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'system'} ${isError ? 'error' : ''}`;

        if (typeof content === 'string') {
            // Handle string content (error messages, etc)
            messageDiv.textContent = content;
        } else if (content.alternatives) {
            // Handle response with alternatives
            console.log('Received response with alternatives:', content);
            messageDiv.innerHTML = `<div class="response-options">
                <h6 class="mb-3">Here are some tailored recommendations:</h6>
            </div>`;

            // Iterate through alternatives and create response options
            content.alternatives.forEach(option => {
                const optionElement = createResponseOption(option, messageInput.value);
                messageDiv.querySelector('.response-options').appendChild(optionElement);
            });
        } else {
            // Handle unexpected content format
            console.error('Unexpected content format:', content);
            messageDiv.textContent = 'Error: Unexpected response format';
        }

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

    function disableSubmit(seconds) {
        submitButton.disabled = true;
        const originalText = submitButton.innerHTML;
        let timeLeft = seconds;

        const interval = setInterval(() => {
            submitButton.innerHTML = `Wait ${timeLeft}s`;
            timeLeft--;

            if (timeLeft < 0) {
                clearInterval(interval);
                submitButton.disabled = false;
                submitButton.innerHTML = originalText;
            }
        }, 1000);
    }

    function handleError(error, loadingMessage) {
        loadingMessage.remove();
        if (error.status === 429) {
            const waitTime = 30; // 30 seconds wait time
            addMessage('The service is currently experiencing high traffic. Please wait 30 seconds before trying again.', false, true);
            disableSubmit(waitTime);
        } else {
            addMessage('Sorry, there was an error processing your request. Please try again.', false, true);
        }
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
            console.log('Sending chat request:', message);
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
            console.log('Received chat response:', data);

            // Remove loading indicator
            loadingMessage.remove();

            if (data.status === 'success') {
                // Pass the entire response object to addMessage
                addMessage(data);
                disableSubmit(5); // 5 second cooldown between requests
            } else {
                handleError({ status: response.status }, loadingMessage);
            }
        } catch (error) {
            console.error('Chat request error:', error);
            handleError(error, loadingMessage);
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
                addMessage('Sorry, there was an error saving your preferences.', false, true);
            }
        } catch (error) {
            addMessage('Sorry, there was an error connecting to the server.', false, true);
        }
    });

    // Check calendar authentication status on page load
    async function checkCalendarAuth() {
        try {
            const response = await fetch('/api/calendar/status');
            const data = await response.json();

            if (data.authenticated) {
                calendarStatus.innerHTML = `
                    <p class="text-success mb-3">
                        <i data-feather="check-circle"></i>
                        Connected to Google Calendar
                    </p>
                    <a href="/api/calendar/logout" class="btn btn-outline-danger btn-sm">
                        <i data-feather="log-out"></i>
                        Disconnect
                    </a>
                `;
                feather.replace();
            }
        } catch (error) {
            console.error('Error checking calendar auth status:', error);
        }
    }

    // Initial check of calendar status
    checkCalendarAuth();
});