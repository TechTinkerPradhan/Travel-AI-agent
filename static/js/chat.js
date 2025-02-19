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

    function addMessage(content, isUser = false, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'system'} ${isError ? 'error' : ''}`;
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
                // Add a small delay between requests
                disableSubmit(5); // 5 second cooldown between requests

                // Check if the response contains travel dates and offer to add to calendar
                if (data.response.toLowerCase().includes('itinerary') || 
                    data.response.toLowerCase().includes('schedule')) {
                    const addToCalendarMsg = document.createElement('div');
                    addToCalendarMsg.className = 'message system';
                    addToCalendarMsg.innerHTML = `
                        <p>Would you like to add this itinerary to your Google Calendar?</p>
                        <button class="btn btn-sm btn-outline-primary add-to-calendar-btn">
                            <i data-feather="calendar"></i> Add to Calendar
                        </button>
                    `;
                    chatMessages.appendChild(addToCalendarMsg);
                    feather.replace();

                    // Add click handler for the calendar button
                    addToCalendarMsg.querySelector('.add-to-calendar-btn').addEventListener('click', async () => {
                        const eventDetails = {
                            summary: 'Travel Itinerary',
                            description: data.response,
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
                }
            } else {
                handleError({ status: response.status }, loadingMessage);
            }
        } catch (error) {
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