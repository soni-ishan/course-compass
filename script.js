// --- Constants ---
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
const chatWindow = document.getElementById('chat-window');
const sendButton = document.getElementById('send-button');
const errorMessageDiv = document.getElementById('error-message');

// !!! IMPORTANT: The Deployed API URL !!!
// Ensure this is the URL of your Render Web Service (the Flask app/API)
const API_BASE_URL = 'https://course-compass-ts9r.onrender.com';


// --- Event Listeners ---
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (message) {
        displayUserMessage(message);
        messageInput.value = '';
        await sendMessageToBackend(message);
    }
});


// --- Display Functions ---
function displayUserMessage(message) {
    const messageElement = `
        <div class="flex items-start gap-3 justify-end">
            <div class="chat-bubble-user p-3 rounded-lg max-w-md">
                <p class="text-sm">${message}</p>
            </div>
            <div class="flex-shrink-0 h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center">
                <i class="fas fa-user text-white"></i>
            </div>
        </div>
    `;
    chatWindow.innerHTML += messageElement;
    scrollToBottom();
}

function displayBotMessage(message) {
    // Sanitize message to prevent HTML injection.
    const sanitizedMessage = message.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const messageElement = `
        <div class="flex items-start gap-3">
            <div class="flex-shrink-0 h-8 w-8 rounded-full bg-gray-700 flex items-center justify-center">
                <i class="fas fa-robot text-white"></i>
            </div>
            <div class="chat-bubble-bot p-3 rounded-lg max-w-md">
                <p class="text-sm">${sanitizedMessage}</p>
            </div>
        </div>
    `;
    chatWindow.innerHTML += messageElement;
    scrollToBottom();
}

function displayLoadingIndicator() {
    const loadingElement = `
        <div id="loading-indicator" class="flex items-start gap-3">
             <div class="flex-shrink-0 h-8 w-8 rounded-full bg-gray-700 flex items-center justify-center">
                <i class="fas fa-robot text-white"></i>
            </div>
            <div class="chat-bubble-bot p-3 rounded-lg">
                <div class="lds-ellipsis"><div></div><div></div><div></div><div></div></div>
            </div>
        </div>
    `;
    chatWindow.innerHTML += loadingElement;
    scrollToBottom();
}

function removeLoadingIndicator() {
    const loadingIndicator = document.getElementById('loading-indicator');
    if (loadingIndicator) {
        loadingIndicator.remove();
    }
}

function displayError(message) {
    errorMessageDiv.textContent = message;
    errorMessageDiv.classList.remove('hidden');
    setTimeout(() => {
        errorMessageDiv.classList.add('hidden');
    }, 5000); // Hide after 5 seconds
}


// --- Helper Functions ---
function scrollToBottom() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
}


// --- API Call ---
async function sendMessageToBackend(message) {
    displayLoadingIndicator();
    sendButton.disabled = true;

    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message }),
        });

        removeLoadingIndicator();

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        displayBotMessage(data.reply);

    } catch (error) {
        console.error('Error:', error);
        removeLoadingIndicator();
        displayBotMessage("Sorry, I'm having trouble connecting to my brain right now. Please try again later.");
        displayError(error.message);
    } finally {
        sendButton.disabled = false;
        messageInput.focus();
    }
}