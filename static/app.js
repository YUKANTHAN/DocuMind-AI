const pdfUpload = document.getElementById('pdf-upload');
const uploadSection = document.getElementById('upload-section');
const chatSection = document.getElementById('chat-section');
const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const filenameSpan = document.getElementById('filename');
const fileInfo = document.getElementById('file-info');
const uploadLoader = document.getElementById('upload-loader');
const statusBadge = document.getElementById('status-badge');
const resetBtn = document.getElementById('reset-upload');

// Auth elements
const authOverlay = document.getElementById('auth-overlay');
const loginEmailInput = document.getElementById('login-email-input');
const simpleLoginBtn = document.getElementById('simple-login-btn');
const userInfo = document.getElementById('user-info');
const userAvatar = document.getElementById('user-avatar');
const userName = document.getElementById('user-name');
const logoutBtn = document.getElementById('logout-btn');

// Settings elements
const settingsBtn = document.getElementById('settings-btn');
const settingsModal = document.getElementById('settings-modal');
const closeModalBtn = document.querySelector('.close-modal');
const systemPromptInput = document.getElementById('system-prompt-input');
const savePromptBtn = document.getElementById('save-prompt-btn');
const resetPromptBtn = document.getElementById('reset-prompt-btn');

// Sidebar & History elements
const sidebar = document.getElementById('sidebar');
const toggleSidebarBtn = document.getElementById('toggle-sidebar');
const docList = document.getElementById('doc-list');

let currentSystemPrompt = "";
const API_BASE = '';
let activeDocId = null;

// --- AUTH LOGIC ---
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/auth/me`);
        const data = await response.json();
        if (data.authenticated) {
            authOverlay.style.opacity = '0';
            setTimeout(() => authOverlay.classList.add('hidden'), 500);
            
            userInfo.style.display = 'flex';
            userAvatar.src = data.user.picture;
            userName.textContent = data.user.name;
            
            // Load history after auth
            loadDocumentHistory();
        } else {
            authOverlay.classList.remove('hidden');
            authOverlay.style.opacity = '1';
            userInfo.style.display = 'none';
        }
    } catch (error) {
        console.error('Auth check failed:', error);
    }
}

simpleLoginBtn.addEventListener('click', async () => {
    const email = loginEmailInput.value.trim();
    if (!email) {
        alert("Please enter a valid email address.");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });

        if (response.ok) {
            checkAuth(); // Refresh state
        } else {
            const data = await response.json();
            alert(`Login failed: ${data.detail}`);
        }
    } catch (error) {
        alert("Login failed. Check your connection.");
    }
});

// Also allow Enter key for login
loginEmailInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') simpleLoginBtn.click();
});

logoutBtn.addEventListener('click', () => {
    window.location.href = `${API_BASE}/auth/logout`;
});

// --- SETTINGS LOGIC ---
settingsBtn.addEventListener('click', async () => {
    if (!currentSystemPrompt) {
        const response = await fetch(`${API_BASE}/prompt/default`);
        const data = await response.json();
        currentSystemPrompt = data.prompt;
    }
    systemPromptInput.value = currentSystemPrompt;
    settingsModal.classList.add('show');
});

closeModalBtn.addEventListener('click', () => settingsModal.classList.remove('show'));

savePromptBtn.addEventListener('click', () => {
    currentSystemPrompt = systemPromptInput.value;
    settingsModal.classList.remove('show');
    addMessage("System prompt updated for future questions.", "system");
});

resetPromptBtn.addEventListener('click', async () => {
    const response = await fetch(`${API_BASE}/prompt/default`);
    const data = await response.json();
    currentSystemPrompt = data.prompt;
    systemPromptInput.value = currentSystemPrompt;
});

// Close modal when clicking outside
window.addEventListener('click', (e) => {
    if (e.target === settingsModal) settingsModal.classList.remove('show');
});

// --- SIDEBAR & HISTORY LOGIC ---
toggleSidebarBtn.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
});

async function loadDocumentHistory() {
    try {
        const response = await fetch(`${API_BASE}/documents`);
        const docs = await response.json();
        
        if (docs.length === 0) {
            docList.innerHTML = '<div class="doc-item empty">No uploads yet</div>';
            return;
        }
        
        docList.innerHTML = docs.map(doc => `
            <div class="doc-item ${doc.id === activeDocId ? 'active' : ''}" onclick="selectDocument(${doc.id})">
                <span class="doc-icon">📄</span> ${doc.filename}
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load docs:', error);
    }
}

async function selectDocument(docId) {
    activeDocId = docId;
    
    // Clear chat UI and show loading
    chatContainer.innerHTML = '<div class="message system-message">Loading history...</div>';
    uploadSection.classList.add('hidden');
    chatSection.classList.remove('hidden');
    
    // Update active state in UI
    document.querySelectorAll('.doc-item').forEach(el => el.classList.remove('active'));
    loadDocumentHistory(); // Re-render to show active state

    try {
        const response = await fetch(`${API_BASE}/documents/${docId}/context`);
        const data = await response.json();
        
        statusBadge.querySelector('.text').textContent = data.filename;
        statusBadge.classList.add('active');
        
        chatContainer.innerHTML = '';
        if (data.history && data.history.length > 0) {
            data.history.forEach(chat => {
                addMessage(chat.question, 'user');
                addMessage(chat.answer, 'system');
            });
        } else {
            addMessage(`Document "${data.filename}" loaded. Ask me anything!`, 'system');
        }
    } catch (error) {
        console.error('Failed to load document context:', error);
        addMessage("Failed to load document. Please try again.", "system");
    }
}

// --- UPLOAD LOGIC ---
pdfUpload.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
        alert('Please upload a PDF file.');
        return;
    }

    uploadLoader.classList.remove('hidden');
    filenameSpan.textContent = file.name;
    fileInfo.classList.remove('hidden');
    document.querySelector('.custom-file-upload').classList.add('hidden');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            activeDocId = data.id;
            statusBadge.querySelector('.text').textContent = file.name;
            statusBadge.classList.add('active');
            
            // Refresh history
            loadDocumentHistory();

            setTimeout(() => {
                uploadSection.classList.add('hidden');
                chatSection.classList.remove('hidden');
                chatContainer.innerHTML = '';
                addMessage(`Document loaded! Ask me anything about "${file.name}".`, 'system');
            }, 800);
        } else {
            alert(`Error: ${data.detail}`);
            resetUpload();
        }
    } catch (error) {
        console.error('Upload failed:', error);
        alert('Upload failed. Is the server running?');
        resetUpload();
    } finally {
        uploadLoader.classList.add('hidden');
    }
});

resetBtn.addEventListener('click', resetUpload);

function resetUpload() {
    pdfUpload.value = '';
    fileInfo.classList.add('hidden');
    document.querySelector('.custom-file-upload').classList.remove('hidden');
    statusBadge.querySelector('.text').textContent = "No Document";
    statusBadge.classList.remove('active');
    uploadSection.classList.remove('hidden');
    chatSection.classList.add('hidden');
    activeDocId = null;
    loadDocumentHistory();
}

// --- CHAT LOGIC ---
async function sendMessage() {
    const question = userInput.value.trim();
    if (!question) return;

    addMessage(question, 'user');
    userInput.value = '';

    const loadingId = addMessage('...', 'system', true);

    try {
        const response = await fetch(`${API_BASE}/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                question,
                system_prompt: currentSystemPrompt || null
            })
        });

        const data = await response.json();
        
        removeMessage(loadingId);
        if (response.ok) {
            addMessage(data.answer, 'system');
        } else {
            addMessage(`Error: ${data.detail}`, 'system');
        }
    } catch (error) {
        removeMessage(loadingId);
        addMessage('Something went wrong. Please check your connection.', 'system');
    }
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

function addMessage(text, type, isLoading = false) {
    const msgDiv = document.createElement('div');
    const id = Date.now();
    msgDiv.id = `msg-${id}`;
    msgDiv.className = `message ${type}-message`;
    
    if (isLoading) {
        msgDiv.innerHTML = '<div class="loader" style="width:20px;height:20px;margin:0"></div>';
    } else {
        msgDiv.innerText = text;
    }
    
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(`msg-${id}`);
    if (el) el.remove();
}

// Make selectDocument global so HTML onclick can find it
window.selectDocument = selectDocument;

// Initial check
checkAuth();
