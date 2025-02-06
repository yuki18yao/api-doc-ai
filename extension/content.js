// Create and inject the chat widget
function createChatWidget() {
    const widget = document.createElement('div');
    widget.id = 'api-doc-ai-widget';
    widget.innerHTML = `
        <div class="widget-header">
            <h3>API Doc AI Assistant</h3>
            <button id="minimize-chat">−</button>
        </div>
        <div class="chat-container">
            <div id="chat-messages"></div>
            <div class="input-container">
                <textarea id="user-input" placeholder="Ask a question about the API..."></textarea>
                <button id="send-message">Send</button>
            </div>
        </div>
    `;
    document.body.appendChild(widget);
    
    // Make the widget draggable
    makeDraggable(widget);
    
    // Initialize chat functionality
    initializeChat();
}

// Make an element draggable
function makeDraggable(element) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    const header = element.querySelector('.widget-header');
    
    header.onmousedown = dragMouseDown;

    function dragMouseDown(e) {
        e.preventDefault();
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
        e.preventDefault();
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        element.style.top = (element.offsetTop - pos2) + "px";
        element.style.left = (element.offsetLeft - pos1) + "px";
    }

    function closeDragElement() {
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

// Initialize chat functionality
function initializeChat() {
    const chatMessages = document.getElementById('chat-messages');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-message');
    const minimizeButton = document.getElementById('minimize-chat');
    
    let conversationHistory = [];

    // Handle minimize/maximize
    minimizeButton.addEventListener('click', () => {
        const chatContainer = document.querySelector('.chat-container');
        if (chatContainer.style.display === 'none') {
            chatContainer.style.display = 'flex';
            minimizeButton.textContent = '−';
        } else {
            chatContainer.style.display = 'none';
            minimizeButton.textContent = '+';
        }
    });

    // Handle sending messages
    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessageToChat('user', message);
        userInput.value = '';

        try {
            const response = await fetch('http://localhost:8000/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question: message,
                    context: document.body.innerText,
                    conversation_history: conversationHistory
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(`Server error: ${JSON.stringify(errorData)}`);
            }
            const data = await response.json();
            addMessageToChat('assistant', data.response);
        } catch (error) {
            const errorMessage = `Error: ${error.message}`;
            addMessageToChat('assistant', errorMessage);
            console.error('Error:', error);
        }
    }

    function addMessageToChat(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;
        
        // For code snippets, wrap them in pre and code tags
        const formattedContent = content.replace(/```([\s\S]*?)```/g, (match, code) => {
            return `<pre><code>${code}</code></pre>`;
        });
        
        messageDiv.innerHTML = formattedContent;
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Add to conversation history
        conversationHistory.push({
            role: role,
            content: content
        });
    }

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Process the current page
    processCurrectPage();
}

// Process the current page
async function processCurrectPage() {
    try {
        await fetch('http://localhost:8000/process-documentation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: window.location.href
            })
        });
    } catch (error) {
        console.error('Error processing page:', error);
    }
}

// Initialize the widget when the page loads
createChatWidget();
