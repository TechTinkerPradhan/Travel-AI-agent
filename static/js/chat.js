document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    const chatMessages = document.getElementById('chatMessages');
    const preferencesForm = document.getElementById('preferencesForm');
    const submitButton = chatForm.querySelector('button[type="submit"]');

    // Generate a simple user ID for demo purposes
    const userId = 'user_' + Math.random().toString(36).substr(2, 9);

    // -------------
    // MAIN HELPERS
    // -------------
    function addMessage(content, isUser = false, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user' : 'system'} ${isError ? 'error' : ''}`;

        if (typeof content === 'string') {
            messageDiv.textContent = content;
        } else if (content.alternatives) {
            // The AI returned multiple itinerary alternatives
            messageDiv.innerHTML = `<div class="response-options">
                <h6 class="mb-3">Here are some tailored recommendations:</h6>
            </div>`;
            content.alternatives.forEach((option) => {
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

    // ---------------
    // SELECT OPTIONS
    // ---------------
    function createResponseOption(optionData) {
        console.log('Creating response option:', optionData);
        const optionDiv = document.createElement('div');
        optionDiv.className = 'message system response-option';

        // Safely parse Markdown
        try {
            optionDiv.innerHTML = marked.parse(optionData.content);
        } catch (e) {
            console.error('Error parsing markdown:', e);
            optionDiv.textContent = optionData.content;
        }

        // "Select This Option" button
        const selectButton = document.createElement('button');
        selectButton.className = 'btn btn-sm btn-outline-primary mt-2 select-response-btn';
        selectButton.innerHTML = '<i data-feather="check"></i> Select this option';
        optionDiv.appendChild(selectButton);

        selectButton.addEventListener('click', async () => {
            // Hide other options
            const allOptions = document.querySelectorAll('.response-option');
            allOptions.forEach(opt => {
                if (opt !== optionDiv) opt.style.display = 'none';
            });

            // Mark this as selected
            selectButton.disabled = true;
            selectButton.innerHTML = '<i data-feather="check"></i> Selected';
            feather.replace();

            // Show refine or confirm
            showRefineOrConfirmButtons(optionData.content, optionDiv);
        });

        feather.replace();
        return optionDiv;
    }

    function showRefineOrConfirmButtons(finalItinerary, parentDiv) {
        // Container for refine text input, refine button, confirm button
        const textExplain = document.createElement('p');
        textExplain.className = 'mt-3';
        textExplain.innerHTML = 'Would you like to make any changes to this plan? <br>Type changes below or click "Confirm Plan" if satisfied.';
        parentDiv.appendChild(textExplain);

        const changesInput = document.createElement('textarea');
        changesInput.className = 'form-control mt-2';
        changesInput.placeholder = 'e.g. Add an extra day in Tokyo, switch Day 2 activities, etc.';
        parentDiv.appendChild(changesInput);

        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'mt-3 d-flex gap-2';

        const refineBtn = document.createElement('button');
        refineBtn.className = 'btn btn-secondary';
        refineBtn.innerHTML = '<i data-feather="edit-2"></i> Refine Plan';

        const confirmBtn = document.createElement('button');
        confirmBtn.className = 'btn btn-success';
        confirmBtn.innerHTML = '<i data-feather="check"></i> Confirm Plan';

        buttonGroup.appendChild(refineBtn);
        buttonGroup.appendChild(confirmBtn);
        parentDiv.appendChild(buttonGroup);
        feather.replace();

        // On refine
        refineBtn.addEventListener('click', () => {
            const changes = changesInput.value.trim();
            if (!changes) return;
            refinePlan(finalItinerary, changes);
        });

        // On confirm
        confirmBtn.addEventListener('click', async () => {
            confirmPlan(finalItinerary, changesInput.value.trim());
        });
    }

    // ---------------
    // REFINING A PLAN
    // ---------------
    async function refinePlan(currentPlan, userChanges) {
        const refinementMessage = `Please revise this plan with the following changes:\n${userChanges}\n\nCurrent plan:\n${currentPlan}`;
        addMessage(refinementMessage, true);

        const loadingMsg = showLoading();
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: refinementMessage,
                    user_id: userId
                })
            });

            // Check if response is ok and content-type is json
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                throw new Error("Server returned non-JSON response");
            }

            const data = await response.json();
            loadingMsg.remove();

            if (data.status === 'success') {
                addMessage(data);
            } else {
                addMessage('Error refining plan: ' + data.message, false, true);
            }
        } catch (error) {
            loadingMsg.remove();
            addMessage('Error refining plan: ' + error.message, false, true);
            console.error('Refinement error:', error);
        }
    }

    // ---------------
    // CONFIRMING A PLAN
    // ---------------
    async function confirmPlan(finalItinerary, userChanges) {
        // Save itinerary to Airtable
        // Then show scheduling modal to pick start date & preview events
        const loadingMsg = showLoading();
        try {
            // Attempt to fetch the last user query from chat
            const userMessages = chatMessages.querySelectorAll('.message.user');
            const lastUserQuery = userMessages.length ? userMessages[userMessages.length - 1].textContent : '(No query found)';

            const saveResponse = await fetch('/api/itinerary/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    original_query: lastUserQuery,
                    selected_itinerary: finalItinerary,
                    user_changes: userChanges
                })
            });
            const saveData = await saveResponse.json();
            loadingMsg.remove();

            if (saveData.status === 'success') {
                addMessage('Plan saved. Now pick a start date to preview events.', false);

                // Show the scheduling modal
                showScheduleModal(finalItinerary);

            } else {
                addMessage('Failed to save itinerary: ' + saveData.message, false, true);
            }
        } catch (error) {
            loadingMsg.remove();
            console.error('Error confirming plan:', error);
            addMessage('Error saving itinerary: ' + error.message, false, true);
        }
    }

    // ---------------
    // SCHEDULING MODAL
    // ---------------
    function showScheduleModal(finalItinerary) {
        // Remove any existing #scheduleModal from DOM
        const existingModalEl = document.getElementById('scheduleModal');
        if (existingModalEl) existingModalEl.remove();

        // Insert modal HTML
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
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        const modalElement = document.getElementById('scheduleModal');
        const bsModal = new bootstrap.Modal(modalElement);
        bsModal.show();

        // On date change -> preview events
        const startDateInput = modalElement.querySelector('#startDate');
        startDateInput.addEventListener('change', async (e) => {
            await updateEventsPreview(finalItinerary, e.target.value);
        });

        // On confirm -> add to calendar
        const confirmScheduleBtn = modalElement.querySelector('#confirmSchedule');
        confirmScheduleBtn.addEventListener('click', async () => {
            const startDate = startDateInput.value;
            if (!startDate) {
                alert('Please select a start date');
                return;
            }

            confirmScheduleBtn.disabled = true;
            confirmScheduleBtn.innerHTML = '<i data-feather="loader"></i> Adding...';
            feather.replace();

            try {
                // Check calendar auth
                const statusRes = await fetch('/api/calendar/status');
                const statusData = await statusRes.json();

                if (!statusData.authenticated) {
                    // Save the itinerary in sessionStorage so after OAuth, we can re-try
                    sessionStorage.setItem('pendingCalendarItinerary', JSON.stringify({
                        itinerary: finalItinerary,
                        startDate: startDate
                    }));
                    window.location.href = '/api/calendar/auth';
                    return;
                }

                // If authenticated, create events
                const res = await fetch('/api/calendar/event', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        itinerary_content: finalItinerary,
                        start_date: startDate
                    })
                });
                const data = await res.json();
                if (data.status === 'success') {
                    addMessage('Successfully added itinerary to your Google Calendar!');
                    bsModal.hide();
                } else {
                    addMessage('Failed to add itinerary to calendar: ' + data.message, false, true);
                    confirmScheduleBtn.disabled = false;
                    confirmScheduleBtn.innerHTML = '<i data-feather="calendar"></i> Add to Calendar';
                    feather.replace();
                }
            } catch (err) {
                console.error('Error creating calendar events:', err);
                addMessage('Error scheduling itinerary: ' + err.message, false, true);
                confirmScheduleBtn.disabled = false;
                confirmScheduleBtn.innerHTML = '<i data-feather="calendar"></i> Add to Calendar';
                feather.replace();
            }
        });

        // Clean up modal
        modalElement.addEventListener('hidden.bs.modal', () => {
            modalElement.remove();
        });
    }

    // ---------------
    // EVENTS PREVIEW
    // ---------------
    async function updateEventsPreview(itinerary, startDate) {
        try {
            const res = await fetch('/api/calendar/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ itinerary_content: itinerary, start_date: startDate })
            });
            const data = await res.json();

            if (data.status === 'success') {
                const eventsList = document.querySelector('#scheduleModal .events-list');
                eventsList.innerHTML = '';
                let currentDay = -1;
                let dayHtml = '';

                data.preview.forEach(evt => {
                    // If new day, add day header
                    if (evt.day_number !== currentDay) {
                        if (dayHtml) {
                            // add the previous dayHtml
                            eventsList.innerHTML += dayHtml;
                        }
                        currentDay = evt.day_number;
                        dayHtml = `
                          <div class="day-header mb-2 mt-3">
                            <h6 class="text-primary">Day ${evt.day_number}: ${evt.day_title}</h6>
                          </div>
                        `;
                    }

                    dayHtml += `
                    <div class="card mb-2">
                      <div class="card-body">
                        <h6 class="card-title">${evt.description}</h6>
                        <div class="text-muted">
                          <small>
                            <i data-feather="clock"></i> ${evt.start_time} (${evt.duration})<br>
                            ${evt.location ? `<i data-feather="map-pin"></i> ${evt.location}` : ''}
                          </small>
                        </div>
                      </div>
                    </div>
                    `;
                });

                // Add the last dayHtml if any
                if (dayHtml) {
                    eventsList.innerHTML += dayHtml;
                }

                feather.replace();
            } else {
                console.error('Preview error:', data.message);
            }
        } catch (error) {
            console.error('Error updating events preview:', error);
        }
    }

    // ---------------
    // FORM SUBMISSIONS
    // ---------------
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const userMessage = messageInput.value.trim();
        if (!userMessage) return;

        addMessage(userMessage, true);
        messageInput.value = '';

        const loadingMessage = showLoading();
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userMessage, user_id: userId })
            });

            // Check if response is ok and content-type is json
            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                throw new Error("Server returned non-JSON response");
            }

            const data = await response.json();
            loadingMessage.remove();

            if (data.status === 'success') {
                addMessage(data);
            } else {
                addMessage('Error: ' + data.message, false, true);
            }
        } catch (err) {
            loadingMessage.remove();
            console.error('Chat error:', err);
            addMessage('Error: ' + err.message, false, true);
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, preferences })
            });
            const data = await response.json();
            if (data.status === 'success') {
                addMessage('Preferences updated successfully! How can I help you plan your trip?');
            } else {
                addMessage('Error saving preferences: ' + data.message, false, true);
            }
        } catch (err) {
            addMessage('Error connecting to server: ' + err.message, false, true);
        }
    });

    // ---------------
    // RE-CHECK AFTER AUTH
    // ---------------
    window.addEventListener('load', async () => {
        // If we stored a pending itinerary in sessionStorage, user might have just returned from Google OAuth
        const pending = sessionStorage.getItem('pendingCalendarItinerary');
        if (pending) {
            const { itinerary, startDate } = JSON.parse(pending);
            sessionStorage.removeItem('pendingCalendarItinerary');

            // Check if we are now authenticated
            const statusRes = await fetch('/api/calendar/status');
            const statusData = await statusRes.json();
            if (statusData.authenticated) {
                // Directly call /api/calendar/event
                try {
                    const res = await fetch('/api/calendar/event', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ itinerary_content: itinerary, start_date: startDate })
                    });
                    const data = await res.json();
                    if (data.status === 'success') {
                        addMessage('Successfully added itinerary to your Google Calendar!');
                    } else {
                        addMessage('Failed to add itinerary to calendar: ' + data.message, false, true);
                    }
                } catch (error) {
                    addMessage('Error adding itinerary to calendar: ' + error.message, false, true);
                }
            }
        }
    });

    // (Optional) Check calendar auth on page load, if you want to update the UI
    async function checkCalendarAuth() {
        try {
            const res = await fetch('/api/calendar/status');
            const data = await res.json();
            // ... update your "calendarStatus" UI ...
        } catch (err) {
            console.error('Error checking calendar auth:', err);
        }
    }
    checkCalendarAuth();
});