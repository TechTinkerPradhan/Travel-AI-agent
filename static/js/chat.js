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

    function createCalendarEventsFromItinerary(content) {
        // Create a dialog to select start date and preview events
        const dialog = document.createElement('div');
        dialog.className = 'modal fade';
        dialog.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Schedule Itinerary Events</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="scheduleForm">
                            <div class="mb-3">
                                <label for="startDate" class="form-label">Start Date for Itinerary</label>
                                <input type="date" class="form-control" id="startDate" required
                                       min="${new Date().toISOString().split('T')[0]}">
                            </div>
                            <div id="eventsPreview" class="mt-4">
                                <h6>Events Preview:</h6>
                                <div class="events-list"></div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" id="confirmSchedule">
                            <i data-feather="calendar"></i> Add to Calendar
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);
        const modal = new bootstrap.Modal(dialog);
        modal.show();

        // Preview events when date is selected
        document.getElementById('startDate').addEventListener('change', async (e) => {
            const startDate = e.target.value;
            try {
                const response = await fetch('/api/calendar/preview', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        itinerary_content: content,
                        start_date: startDate
                    })
                });

                const data = await response.json();
                if (data.status === 'success') {
                    // Display events preview
                    const eventsList = dialog.querySelector('.events-list');
                    eventsList.innerHTML = data.preview.map(event => `
                        <div class="card mb-2">
                            <div class="card-body">
                                <h6 class="card-title">${event.summary}</h6>
                                <div class="text-muted">
                                    <small>
                                        <i data-feather="clock"></i> ${event.start_time} (${event.duration})
                                        ${event.location ? `<br><i data-feather="map-pin"></i> ${event.location}` : ''}
                                    </small>
                                </div>
                            </div>
                        </div>
                    `).join('');
                    feather.replace();
                }
            } catch (error) {
                console.error('Error getting events preview:', error);
            }
        });

        // Handle form submission
        document.getElementById('confirmSchedule').addEventListener('click', async () => {
            const startDate = document.getElementById('startDate').value;
            if (!startDate) {
                alert('Please select a start date');
                return;
            }

            try {
                const confirmBtn = document.getElementById('confirmSchedule');
                confirmBtn.disabled = true;
                confirmBtn.innerHTML = '<i data-feather="loader"></i> Adding to Calendar...';
                feather.replace();

                const response = await fetch('/api/calendar/event', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        itinerary_content: content,
                        start_date: startDate
                    })
                });

                const data = await response.json();
                if (data.status === 'success') {
                    addMessage('Successfully added itinerary to your Google Calendar!');
                    modal.hide();
                    dialog.remove();
                } else {
                    addMessage('Failed to add itinerary to calendar: ' + data.message, false, true);
                    confirmBtn.disabled = false;
                    confirmBtn.innerHTML = '<i data-feather="calendar"></i> Add to Calendar';
                    feather.replace();
                }
            } catch (error) {
                console.error('Error creating calendar events:', error);
                addMessage('Error scheduling itinerary: ' + error.message, false, true);
                confirmBtn.disabled = false;
                confirmBtn.innerHTML = '<i data-feather="calendar"></i> Add to Calendar';
                feather.replace();
            }
        });

        // Clean up when dialog is closed
        dialog.addEventListener('hidden.bs.modal', () => {
            dialog.remove();
        });
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

        // Add calendar button if this is an itinerary
        if (optionData.type === 'itinerary') {
            const calendarButton = document.createElement('button');
            calendarButton.className = 'btn btn-sm btn-outline-secondary mt-2 ms-2';
            calendarButton.innerHTML = '<i data-feather="calendar"></i> Add to Calendar';

            calendarButton.addEventListener('click', async () => {
                // Show loading state
                calendarButton.disabled = true;
                calendarButton.innerHTML = '<i data-feather="loader"></i> Connecting...';
                feather.replace();

                try {
                    // Check calendar auth status first
                    const statusResponse = await fetch('/api/calendar/status');
                    const statusData = await statusResponse.json();

                    if (!statusData.authenticated) {
                        // Redirect to Google auth
                        window.location.href = '/api/calendar/auth';
                    } else {
                        createCalendarEventsFromItinerary(optionData.content);
                    }
                } catch (error) {
                    console.error('Error checking calendar status:', error);
                    addMessage('Failed to connect to Google Calendar. Please try again.', false, true);

                    // Reset button state
                    calendarButton.disabled = false;
                    calendarButton.innerHTML = '<i data-feather="calendar"></i> Add to Calendar';
                    feather.replace();
                }
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

                // Disable the button and show loading state
                selectButton.disabled = true;
                selectButton.innerHTML = '<i data-feather="loader"></i> Selecting...';
                feather.replace();

                const queryText = messageInput.value.trim();
                const response = await fetch('/api/chat/select', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        user_id: userId,
                        original_query: queryText,
                        selected_response: optionData.content
                    })
                });

                const data = await response.json();
                console.log('Selection response:', data);

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
                    selectButton.classList.remove('btn-outline-primary');
                    selectButton.classList.add('btn-success');
                    selectButton.innerHTML = '<i data-feather="check-circle"></i> Selected';
                    feather.replace();

                    // Add friendly confirmation message
                    const confirmationMessage = document.createElement('div');
                    confirmationMessage.className = 'message system mt-3';
                    confirmationMessage.innerHTML = `
                        <div class="confirmation-banner">
                            <i data-feather="check-circle" class="text-success"></i>
                            <h5 class="mb-2">Excellent choice! 🎉</h5>
                            <p class="mb-2">I'm excited to help you with this wonderful itinerary! Would you like me to add these plans to your Google Calendar? Just click the "Add to Calendar" button, and I'll take care of scheduling everything for you.</p>
                            <p class="mb-0">Feel free to ask me any questions about the itinerary or if you'd like to make any adjustments to better suit your preferences!</p>
                        </div>
                    `;
                    chatMessages.appendChild(confirmationMessage);
                    feather.replace();

                    // Add preference analysis if available
                    if (data.preference_analysis) {
                        const analysisDiv = document.createElement('div');
                        analysisDiv.className = 'message system preference-analysis mt-2';
                        analysisDiv.innerHTML = `
                            <small class="text-muted">Your travel preferences:</small>
                            <pre>${JSON.stringify(JSON.parse(data.preference_analysis), null, 2)}</pre>
                        `;
                        chatMessages.appendChild(analysisDiv);
                    }
                } else {
                    console.error('Error selecting response:', data);
                    selectButton.disabled = false;
                    selectButton.innerHTML = '<i data-feather="check"></i> Select this option';
                    feather.replace();
                    addMessage('Error processing your selection. Please try again.', false, true);
                }
            } catch (error) {
                console.error('Error selecting response:', error);
                selectButton.disabled = false;
                selectButton.innerHTML = '<i data-feather="check"></i> Select this option';
                feather.replace();
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

    // Update the calendar authentication handling
    function checkCalendarAuth() {
        try {
            console.log("Checking Google Calendar authentication status...");
            fetch('/api/calendar/status')
                .then(response => response.json())
                .then(data => {
                    console.log("Calendar auth status response:", data);
                    const calendarStatus = document.getElementById('calendarStatus');
                    const calendarAuthBtn = document.getElementById('calendarAuthBtn');

                    if (!calendarStatus || !calendarAuthBtn) {
                        console.error('Calendar status elements not found in DOM');
                        return;
                    }

                    if (data.authenticated) {
                        console.log('User is authenticated with Google Calendar');
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
                    } else {
                        console.log('User is not authenticated with Google Calendar');
                        const authButton = document.createElement('a');
                        authButton.href = '/api/calendar/auth';
                        authButton.className = 'btn btn-primary btn-sm';
                        authButton.innerHTML = `
                            <i data-feather="calendar"></i>
                            Connect Google Calendar
                        `;
                        authButton.addEventListener('click', (e) => {
                            console.log('Connect Google Calendar button clicked');
                            // Let the default navigation happen
                        });

                        calendarStatus.innerHTML = `
                            <p class="text-warning mb-3">
                                <i data-feather="alert-circle"></i>
                                Not connected to Google Calendar
                            </p>
                        `;
                        calendarStatus.appendChild(authButton);
                    }
                    feather.replace();
                })
                .catch(error => {
                    console.error('Error checking calendar auth status:', error);
                    calendarStatus.innerHTML = `
                        <p class="text-danger mb-3">
                            <i data-feather="alert-triangle"></i>
                            Error connecting to Google Calendar
                        </p>
                        <a href="/api/calendar/auth" class="btn btn-primary btn-sm">
                            <i data-feather="refresh-cw"></i>
                            Try Again
                        </a>
                    `;
                    feather.replace();
                });
        } catch (error) {
            console.error('Error in checkCalendarAuth:', error);
        }
    }

    // Check calendar auth status when page loads
    checkCalendarAuth();
});