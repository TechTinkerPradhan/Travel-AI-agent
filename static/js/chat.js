document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    const chatMessages = document.getElementById('chatMessages');
    const preferencesForm = document.getElementById('preferencesForm');
    const submitButton = chatForm.querySelector('button[type="submit"]');

    // Generate a simple user ID for demo purposes
    const userId = 'user_' + Math.random().toString(36).substr(2, 9);

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
        optionDiv.appendChild(selectButton);

        selectButton.addEventListener('click', async () => {
            selectButton.disabled = true;
            selectButton.innerHTML = '<i data-feather="loader"></i> Processing...';
            feather.replace();

            // Hide other options
            const allOptions = document.querySelectorAll('.response-option');
            allOptions.forEach(option => {
                if (option !== optionDiv) {
                    option.style.display = 'none';
                }
            });

            // Create confirm plan button
            const confirmButton = document.createElement('button');
            confirmButton.className = 'btn btn-success mt-3';
            confirmButton.innerHTML = '<i data-feather="check"></i> Confirm Plan';
            optionDiv.appendChild(confirmButton);
            feather.replace();

            // Ask if user wants to make changes
            const confirmText = document.createElement('div');
            confirmText.className = 'mt-3';
            confirmText.innerHTML = 'Would you like to make any changes to this plan? <br>If yes, please type your changes below:';
            optionDiv.appendChild(confirmText);

            // Add text area for changes
            const changesInput = document.createElement('textarea');
            changesInput.className = 'form-control mt-2';
            changesInput.placeholder = 'e.g., Add an extra day in Tokyo, or switch Day 2 activities...';
            optionDiv.appendChild(changesInput);

            // Create button group for actions
            const buttonGroup = document.createElement('div');
            buttonGroup.className = 'd-flex gap-2 mt-3';

            // Add "Refine Plan" button
            const refineButton = document.createElement('button');
            refineButton.className = 'btn btn-secondary';
            refineButton.innerHTML = '<i data-feather="edit-2"></i> Refine Plan';
            buttonGroup.appendChild(refineButton);

            // Add confirm button to group
            buttonGroup.appendChild(confirmButton);
            optionDiv.appendChild(buttonGroup);
            feather.replace();

            try {
                // Get the original query
                const queryMessage = chatMessages.querySelector('.message.user:last-child')?.textContent;

                // Handle refinement
                refineButton.addEventListener('click', () => {
                    const changes = changesInput.value.trim();
                    if (changes) {
                        refinePlan(optionData.content, changes);
                    }
                });

                // Handle confirmation
                confirmButton.addEventListener('click', async () => {
                    await confirmPlan(optionData.content, changesInput.value.trim(), queryMessage);
                });

            } catch (error) {
                console.error('Error processing selection:', error);
                addMessage('Error processing your selection. Please try again.', false, true);
            }
        });

        feather.replace();
        return optionDiv;
    }

    async function refinePlan(currentPlan, changes) {
        const refinementMessage = `Please revise this plan with the following changes:\n${changes}\n\nCurrent plan:\n${currentPlan}`;
        addMessage(changes, true);

        const loadingMsg = showLoading();
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: refinementMessage,
                    user_id: userId
                })
            });

            const data = await response.json();
            loadingMsg.remove();

            if (data.status === 'success') {
                addMessage(data);
            } else {
                addMessage('Error refining plan: ' + data.message, false, true);
            }
        } catch (error) {
            loadingMsg.remove();
            addMessage('Error: ' + error.message, false, true);
        }
    }

    async function confirmPlan(finalItinerary, userChanges, originalQuery) {
        try {
            const saveResponse = await fetch('/api/itinerary/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    user_id: userId,
                    original_query: originalQuery,
                    selected_itinerary: finalItinerary,
                    user_changes: userChanges
                })
            });

            const saveData = await saveResponse.json();
            if (saveData.status === 'success') {
                // Create a dialog to select start date and preview events
                const modalHtml = `
                    <div class="modal fade" id="scheduleModal" tabindex="-1" aria-labelledby="scheduleModalLabel" aria-hidden="true">
                        <div class="modal-dialog modal-lg">
                            <div class="modal-content">
                                <div class="modal-header">
                                    <h5 class="modal-title" id="scheduleModalLabel">Schedule Itinerary Events</h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
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
                    </div>
                `;

                // Remove any existing modal
                const existingModal = document.getElementById('scheduleModal');
                if (existingModal) {
                    existingModal.remove();
                }

                // Add the modal to the document
                document.body.insertAdjacentHTML('beforeend', modalHtml);

                // Get the modal element
                const modalElement = document.getElementById('scheduleModal');

                // Initialize Bootstrap modal
                const modal = new bootstrap.Modal(modalElement);

                // Show the modal
                modal.show();

                // Preview events when date is selected
                document.getElementById('startDate').addEventListener('change', async (e) => {
                    await updateEventsPreview(finalItinerary, e.target.value);
                });

                // Handle schedule confirmation
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

                        // Check calendar auth status
                        const statusResponse = await fetch('/api/calendar/status');
                        const statusData = await statusResponse.json();

                        if (!statusData.authenticated) {
                            // Store the current state before redirecting
                            sessionStorage.setItem('pendingCalendarItinerary', JSON.stringify({
                                itinerary: finalItinerary,
                                startDate: startDate
                            }));
                            window.location.href = '/api/calendar/auth';
                            return;
                        }

                        const response = await fetch('/api/calendar/event', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                itinerary_content: finalItinerary,
                                start_date: startDate
                            })
                        });

                        const data = await response.json();
                        if (data.status === 'success') {
                            addMessage('Successfully added itinerary to your Google Calendar!');
                            modal.hide();
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

                // Clean up when modal is hidden
                modalElement.addEventListener('hidden.bs.modal', () => {
                    modalElement.remove();
                });

            } else {
                addMessage('Failed to save itinerary: ' + saveData.message, false, true);
            }
        } catch (error) {
            console.error('Error confirming plan:', error);
            addMessage('Error saving itinerary: ' + error.message, false, true);
        }
    }

    async function updateEventsPreview(itinerary, startDate) {
        try {
            const response = await fetch('/api/calendar/preview', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    itinerary_content: itinerary,
                    start_date: startDate
                })
            });

            const data = await response.json();
            if (data.status === 'success') {
                const eventsList = document.querySelector('#scheduleModal .events-list');
                let currentDayNumber = null;
                let eventsHtml = '';

                data.preview.forEach(event => {
                    // Add day header if it's a new day
                    if (currentDayNumber !== event.day_number) {
                        currentDayNumber = event.day_number;
                        eventsHtml += `
                            <div class="day-header mb-3">
                                <h6 class="text-primary">Day ${event.day_number}: ${event.day_title}</h6>
                            </div>
                        `;
                    }

                    // Add event card
                    eventsHtml += `
                        <div class="card mb-2">
                            <div class="card-body">
                                <div class="d-flex justify-content-between align-items-start">
                                    <div>
                                        <h6 class="card-title mb-2">${event.description}</h6>
                                        <div class="text-muted">
                                            <small>
                                                <i data-feather="clock"></i> ${event.start_time} (${event.duration})
                                                ${event.location ? `<br><i data-feather="map-pin"></i> ${event.location}` : ''}
                                            </small>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                });

                eventsList.innerHTML = eventsHtml;
                feather.replace();
            }
        } catch (error) {
            console.error('Error getting events preview:', error);
        }
    }

    async function handleScheduleConfirmation(itinerary, startDate) {
        if (!startDate) {
            alert('Please select a start date');
            return;
        }

        try {
            const confirmBtn = document.getElementById('confirmSchedule');
            confirmBtn.disabled = true;
            confirmBtn.innerHTML = '<i data-feather="loader"></i> Adding to Calendar...';
            feather.replace();

            // Check calendar auth status
            const statusResponse = await fetch('/api/calendar/status');
            const statusData = await statusResponse.json();

            if (!statusData.authenticated) {
                // Store the current state before redirecting
                sessionStorage.setItem('pendingCalendarItinerary', JSON.stringify({
                    itinerary: itinerary,
                    startDate: startDate
                }));
                window.location.href = '/api/calendar/auth';
                return;
            }

            const response = await fetch('/api/calendar/event', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    itinerary_content: itinerary,
                    start_date: startDate
                })
            });

            const data = await response.json();
            if (data.status === 'success') {
                addMessage('Successfully added itinerary to your Google Calendar!');
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
    }

    function addMessage(content, isUser = false, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'system'} ${isError ? 'error' : ''}`;

        if (typeof content === 'string') {
            messageDiv.textContent = content;
        } else if (content.alternatives) {
            messageDiv.innerHTML = `<div class="response-options">
                <h6 class="mb-3">Here are some tailored recommendations:</h6>
            </div>`;

            content.alternatives.forEach(option => {
                const optionElement = createResponseOption(option);
                messageDiv.querySelector('.response-options').appendChild(optionElement);
            });
        } else {
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

    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const message = messageInput.value.trim();
        if (!message) return;

        addMessage(message, true);
        messageInput.value = '';

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
            loadingMessage.remove();

            if (data.status === 'success') {
                addMessage(data);
            } else {
                addMessage('Error: ' + data.message, false, true);
            }
        } catch (error) {
            loadingMessage.remove();
            addMessage('Error: ' + error.message, false, true);
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
                addMessage('Error saving preferences: ' + data.message, false, true);
            }
        } catch (error) {
            addMessage('Error connecting to server: ' + error.message, false, true);
        }
    });

    // Check for pending calendar operations after OAuth
    window.addEventListener('load', async () => {
        const pendingCalendarItinerary = sessionStorage.getItem('pendingCalendarItinerary');
        if (pendingCalendarItinerary) {
            const { itinerary, startDate } = JSON.parse(pendingCalendarItinerary);
            sessionStorage.removeItem('pendingCalendarItinerary');

            const statusResponse = await fetch('/api/calendar/status');
            const statusData = await statusResponse.json();

            if (statusData.authenticated) {
                await handleScheduleConfirmation(itinerary, startDate);
            }
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

    //Helper function to get user ID (assuming this function exists elsewhere)
    function getUserId() {
        //Implementation to retrieve userId
        return userId;
    }

    async function sendMessage(message) {
        try {
            console.log("Sending chat request:", message);


            //Regular message sending
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
            addMessage(data);
        } catch (error) {
            console.error('Error sending message:', error);
            addMessage('Error sending message: ' + error.message, false, true);
        }
    }
});