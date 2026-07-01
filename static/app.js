// ── State Management ──
let activeSessionId = null;
let activeCompany = null; // Tracks the current active context (null = All / picker state)
let companiesList = [];
let sessionsList = [];
let llmSettings = {
    provider: 'gemini',
    model: '',
    api_key: '',
    api_url: '',
    serper_api_key: ''
};
let currentUser = null;

// ── DOM Elements ──
const loginScreen = document.getElementById('loginScreen');
const appContainer = document.getElementById('appContainer');
const loginEmail = document.getElementById('loginEmail');
const loginPassword = document.getElementById('loginPassword');
const loginError = document.getElementById('loginError');
const loginBtn = document.getElementById('loginBtn');
const userEmailDisplay = document.getElementById('userEmailDisplay');
const logoutBtn = document.getElementById('logoutBtn');

const sidebar = document.getElementById('sidebar');
const menuToggle = document.getElementById('menuToggle');
const newChatBtn = document.getElementById('newChatBtn');
const historyList = document.getElementById('historyList');
const companyList = document.getElementById('companyList');
const companySearch = document.getElementById('companySearch');
const activeCompanyBadge = document.getElementById('activeCompanyBadge');
const resetContextBtn = document.getElementById('resetContextBtn');
const chatWindow = document.getElementById('chatWindow');

// Welcome containers
const companyPickerContainer = document.getElementById('companyPickerContainer');
const companyPickerGrid = document.getElementById('companyPickerGrid');
const companyPickerGreeting = document.getElementById('companyPickerGreeting');
const pickerSearch = document.getElementById('pickerSearch');
const welcomeContainer = document.getElementById('welcomeContainer');
const messagesContainer = document.getElementById('messagesContainer');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const suggestedGrid = document.getElementById('suggestedGrid');

// Modals
const settingsModal = document.getElementById('settingsModal');
const openSettingsBtn = document.getElementById('openSettingsBtn');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');
const llmProvider = document.getElementById('llmProvider');
const llmApiKey = document.getElementById('llmApiKey');
const llmModel = document.getElementById('llmModel');
const llmApiUrl = document.getElementById('llmApiUrl');
const apiKeyGroup = document.getElementById('apiKeyGroup');
const apiUrlGroup = document.getElementById('apiUrlGroup');
const serperApiKeyInput = document.getElementById('serperApiKey');

const uploadModal = document.getElementById('uploadModal');
const openUploadBtn = document.getElementById('openUploadBtn');
const closeUploadBtn = document.getElementById('closeUploadBtn');
const cancelUploadBtn = document.getElementById('cancelUploadBtn');
const startUploadBtn = document.getElementById('startUploadBtn');
const dragDropArea = document.getElementById('dragDropArea');
const fileInput = document.getElementById('fileInput');
const selectedFilesList = document.getElementById('selectedFilesList');
const uploadCompanySelect = document.getElementById('uploadCompanySelect');
const uploadCompanyInput = document.getElementById('uploadCompanyInput');
const uploadProgressContainer = document.getElementById('uploadProgressContainer');
const uploadProgressBar = document.getElementById('uploadProgressBar');
const uploadStatusText = document.getElementById('uploadStatusText');

// ── Initialization ──
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    initializeEventListeners();
    checkAuth();
});

// ── Auth Check ──
async function checkAuth() {
    const token = localStorage.getItem('auth_token');
    if (!token) {
        showLoginScreen();
        return;
    }

    try {
        const res = await fetch('/api/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.status === 200) {
            currentUser = await res.json();
            showAppScreen();
        } else {
            logout();
        }
    } catch (e) {
        console.error('Auth verification failed:', e);
        showLoginScreen();
    }
}

function showLoginScreen() {
    loginScreen.classList.remove('hidden');
    appContainer.classList.add('hidden');
}

function showAppScreen() {
    loginScreen.classList.add('hidden');
    appContainer.classList.remove('hidden');
    
    // Display Username (Email Prefix)
    const emailPrefix = currentUser.email.split('@')[0];
    userEmailDisplay.textContent = emailPrefix;
    companyPickerGreeting.textContent = `👋 Hi ${emailPrefix}, where are you interviewing?`;
    
    loadSessions(true);
    loadCompanies();
}

function logout() {
    localStorage.removeItem('auth_token');
    currentUser = null;
    showLoginScreen();
}

// ── Authenticated API Wrapper ──
async function apiFetch(url, options = {}) {
    const token = localStorage.getItem('auth_token');
    if (!options.headers) options.headers = {};
    if (token) {
        options.headers['Authorization'] = `Bearer ${token}`;
    }
    
    const res = await fetch(url, options);
    if (res.status === 401) {
        showToast('Session expired. Please log in again.');
        logout();
        throw new Error('Unauthorized');
    }
    return res;
}

// ── Event Listeners ──
function initializeEventListeners() {
    // Login Button
    loginBtn.addEventListener('click', handleLogin);
    loginPassword.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') handleLogin();
    });

    // Logout Button
    logoutBtn.addEventListener('click', logout);

    // Mobile Sidebar Toggle
    menuToggle.addEventListener('click', () => {
        sidebar.classList.toggle('active');
    });

    // Close sidebar if clicking outside on mobile
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 768) {
            if (sidebar && !sidebar.contains(e.target) && !menuToggle.contains(e.target) && sidebar.classList.contains('active')) {
                sidebar.classList.remove('active');
            }
        }
    });

    // New Chat
    newChatBtn.addEventListener('click', createNewSession);

    // Context Reset
    resetContextBtn.addEventListener('click', () => {
        setCompanyContext(null);
    });

    // Company Search
    companySearch.addEventListener('input', (e) => {
        filterCompanies(e.target.value);
    });

    // Company Picker Search
    pickerSearch.addEventListener('input', (e) => {
        filterPickerCompanies(e.target.value);
    });

    // Input Textarea Autogrow & Keybindings
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = (chatInput.scrollHeight) + 'px';
        sendBtn.disabled = !chatInput.value.trim() || activeCompany === null;
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (activeCompany !== null) {
                sendMessage();
            }
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    // ── Settings Modal Events ──
    openSettingsBtn.addEventListener('click', () => {
        llmProvider.value = llmSettings.provider;
        llmApiKey.value = llmSettings.api_key;
        llmModel.value = llmSettings.model;
        llmApiUrl.value = llmSettings.api_url;
        serperApiKeyInput.value = llmSettings.serper_api_key || '';
        toggleSettingsFields();
        settingsModal.classList.add('active');
    });

    closeSettingsBtn.addEventListener('click', () => settingsModal.classList.remove('active'));
    cancelSettingsBtn.addEventListener('click', () => settingsModal.classList.remove('active'));
    
    llmProvider.addEventListener('change', toggleSettingsFields);
    
    saveSettingsBtn.addEventListener('click', () => {
        llmSettings.provider = llmProvider.value;
        llmSettings.api_key = llmApiKey.value;
        llmSettings.model = llmModel.value;
        llmSettings.api_url = llmApiUrl.value;
        llmSettings.serper_api_key = serperApiKeyInput.value.trim();
        localStorage.setItem('llm_settings', JSON.stringify(llmSettings));
        settingsModal.classList.remove('active');
        showToast('Settings saved successfully!');
    });

    // ── Upload Modal Events ──
    openUploadBtn.addEventListener('click', () => {
        uploadCompanySelect.innerHTML = '<option value="">-- Create New Folder / Choose --</option>';
        companiesList.forEach(company => {
            const opt = document.createElement('option');
            opt.value = company;
            opt.textContent = company;
            uploadCompanySelect.appendChild(opt);
        });
        uploadCompanyInput.value = '';
        selectedFilesList.innerHTML = '';
        fileInput.value = '';
        uploadProgressContainer.style.display = 'none';
        uploadProgressBar.style.width = '0%';
        uploadStatusText.textContent = '';
        uploadModal.classList.add('active');
    });

    closeUploadBtn.addEventListener('click', () => uploadModal.classList.remove('active'));
    cancelUploadBtn.addEventListener('click', () => uploadModal.classList.remove('active'));

    // File Input Browse
    dragDropArea.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', () => {
        renderSelectedFiles();
    });

    // Drag and Drop
    dragDropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dragDropArea.classList.add('dragover');
    });

    dragDropArea.addEventListener('dragleave', () => {
        dragDropArea.classList.remove('dragover');
    });

    dragDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dragDropArea.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            renderSelectedFiles();
        }
    });

    startUploadBtn.addEventListener('click', handleUpload);
}

// ── Login Handler ──
async function handleLogin() {
    const email = loginEmail.value.trim();
    const password = loginPassword.value;
    
    loginError.textContent = '';
    
    if (!email || !password) {
        loginError.textContent = 'Please fill in all fields.';
        return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = 'Verifying...';

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await res.json();
        
        if (res.status === 200) {
            localStorage.setItem('auth_token', data.access_token);
            currentUser = data.user;
            showAppScreen();
        } else {
            loginError.textContent = data.detail || 'Login failed.';
        }
    } catch (e) {
        loginError.textContent = 'Could not connect to authentication server.';
        console.error(e);
    } finally {
        loginBtn.disabled = false;
        loginBtn.textContent = 'Login →';
    }
}

// ── LLM Settings Helper ──
function loadSettings() {
    const saved = localStorage.getItem('llm_settings');
    if (saved) {
        try {
            llmSettings = JSON.parse(saved);
        } catch (e) {
            console.error('Error parsing LLM settings', e);
        }
    }
}

function toggleSettingsFields() {
    const provider = llmProvider.value;
    if (provider === 'gemini') {
        apiKeyGroup.style.display = 'flex';
        apiKeyLabel.textContent = 'Gemini API Key';
        apiUrlGroup.style.display = 'none';
        if (!llmModel.value) llmModel.placeholder = 'e.g. gemini-2.5-flash';
    } else if (provider === 'openai') {
        apiKeyGroup.style.display = 'flex';
        apiKeyLabel.textContent = 'OpenAI API Key';
        apiUrlGroup.style.display = 'none';
        if (!llmModel.value) llmModel.placeholder = 'e.g. gpt-4o';
    } else if (provider === 'ollama') {
        apiKeyGroup.style.display = 'none';
        apiUrlGroup.style.display = 'flex';
        if (!llmModel.value) llmModel.placeholder = 'e.g. llama3';
    }
}

// ── Fetch & Render Sessions ──
async function loadSessions(selectFirst = false) {
    try {
        const res = await apiFetch('/api/history');
        const sessions = await res.json();
        sessionsList = sessions;
        renderSessions();

        if (selectFirst && sessions.length > 0) {
            selectSession(sessions[0].id);
        }
    } catch (e) {
        console.error('Error loading chat history:', e);
    }
}

function renderSessions() {
    historyList.innerHTML = '';
    sessionsList.forEach(session => {
        const item = document.createElement('div');
        item.className = `session-item ${session.id === activeSessionId ? 'active' : ''}`;
        item.dataset.id = session.id;
        
        item.innerHTML = `
            <div class="item-content">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                <span>${escapeHtml(session.title)}</span>
            </div>
            <button class="item-delete-btn" title="Delete Chat">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
            </button>
        `;

        item.addEventListener('click', (e) => {
            if (e.target.closest('.item-delete-btn')) {
                e.stopPropagation();
                deleteSession(session.id);
            } else {
                selectSession(session.id);
            }
        });

        historyList.appendChild(item);
    });
}

async function selectSession(sessionId) {
    activeSessionId = sessionId;
    document.querySelectorAll('.session-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === sessionId);
    });

    try {
        const res = await apiFetch(`/api/history/${sessionId}`);
        const data = await res.json();
        
        messagesContainer.innerHTML = '';
        if (data.messages && data.messages.length > 0) {
            // Find context from last user message or default
            let lastCompany = null;
            for (let i = data.messages.length - 1; i >= 0; i--) {
                if (data.messages[i].role === 'user' && data.messages[i].company) {
                    lastCompany = data.messages[i].company;
                    break;
                }
            }
            setCompanyContext(lastCompany, false); // select context but don't clear list
            
            companyPickerContainer.style.display = 'none';
            welcomeContainer.style.display = 'none';
            messagesContainer.style.display = 'flex';
            
            data.messages.forEach(msg => {
                appendMessageBubble(msg.role, msg.content, msg.company);
            });
            enableChatInput();
        } else {
            // New chat session
            setCompanyContext(null, false);
            showCompanyPicker();
        }
        scrollToBottom();
    } catch (e) {
        console.error('Error fetching session messages:', e);
    }
}

async function createNewSession() {
    try {
        const res = await apiFetch('/api/history/new', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const newSession = await res.json();
        activeSessionId = newSession.id;
        
        sessionsList.unshift(newSession);
        renderSessions();
        selectSession(newSession.id);
        
        if (window.innerWidth <= 768) {
            sidebar.classList.remove('active');
        }
    } catch (e) {
        console.error('Error creating new session:', e);
    }
}

async function deleteSession(sessionId) {
    if (!confirm('Are you sure you want to delete this chat session?')) return;
    try {
        await apiFetch(`/api/history/${sessionId}`, { method: 'DELETE' });
        
        sessionsList = sessionsList.filter(s => s.id !== sessionId);
        renderSessions();

        if (activeSessionId === sessionId) {
            if (sessionsList.length > 0) {
                selectSession(sessionsList[0].id);
            } else {
                createNewSession();
            }
        }
    } catch (e) {
        console.error('Error deleting session:', e);
    }
}

// ── Fetch & Render Companies ──
async function loadCompanies() {
    try {
        const res = await apiFetch('/api/companies');
        const data = await res.json();
        companiesList = data.companies;
        renderCompanies();
        renderCompanyPickerGrid();
    } catch (e) {
        console.error('Error loading companies:', e);
    }
}

function renderCompanies() {
    companyList.innerHTML = '';
    
    // Add "All Companies" option at the top
    const allItem = document.createElement('div');
    allItem.className = `company-item ${activeCompany === null ? 'active' : ''}`;
    allItem.innerHTML = `
        <div class="item-content">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            <span>All Companies</span>
        </div>
    `;
    allItem.addEventListener('click', () => setCompanyContext(null));
    companyList.appendChild(allItem);

    companiesList.forEach(company => {
        const item = document.createElement('div');
        item.className = `company-item ${company === activeCompany ? 'active' : ''}`;
        item.dataset.name = company;
        item.innerHTML = `
            <div class="item-content">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>
                <span>${escapeHtml(company)}</span>
            </div>
            <button class="company-scrape-btn" title="Scrape Web Feedback">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
            </button>
        `;
        item.addEventListener('click', (e) => {
            if (e.target.closest('.company-scrape-btn')) {
                e.stopPropagation();
                triggerCompanyScrape(company, e.target.closest('.company-scrape-btn'));
            } else {
                setCompanyContext(company);
            }
        });
        companyList.appendChild(item);
    });
}

// ── Company Picker Rendering ──
function showCompanyPicker() {
    companyPickerContainer.style.display = 'flex';
    welcomeContainer.style.display = 'none';
    messagesContainer.style.display = 'none';
    
    // Disable text area until company selected
    chatInput.placeholder = "Select a company from the list above first...";
    chatInput.disabled = true;
    sendBtn.disabled = true;
    pickerSearch.value = '';
    filterPickerCompanies('');
}

function renderCompanyPickerGrid() {
    companyPickerGrid.innerHTML = '';
    
    // All Companies Card
    const allCard = document.createElement('div');
    allCard.className = 'picker-card all-card';
    allCard.innerHTML = `
        <div class="picker-card-logo">🔍</div>
        <div class="picker-card-name">All Companies</div>
        <div class="picker-card-desc">Search information across all CIT seniors' experiences</div>
    `;
    allCard.addEventListener('click', () => {
        setCompanyContext(null);
    });
    companyPickerGrid.appendChild(allCard);

    companiesList.forEach(company => {
        const card = document.createElement('div');
        card.className = 'picker-card';
        card.dataset.name = company;
        card.innerHTML = `
            <div class="picker-card-logo">🏢</div>
            <div class="picker-card-name">${escapeHtml(company)}</div>
            <div class="picker-card-desc">Prepare for ${escapeHtml(company)} placement rounds</div>
        `;
        card.addEventListener('click', () => {
            setCompanyContext(company);
        });
        companyPickerGrid.appendChild(card);
    });
}

function filterPickerCompanies(query) {
    const term = query.toLowerCase();
    document.querySelectorAll('.company-picker-grid .picker-card').forEach(el => {
        const name = el.dataset.name;
        if (!name) return; // Keep "All Companies"
        if (name.toLowerCase().includes(term)) {
            el.style.display = 'flex';
        } else {
            el.style.display = 'none';
        }
    });
}

function enableChatInput() {
    chatInput.disabled = false;
    chatInput.placeholder = `Message PlacementGPT about ${activeCompany || 'All Companies'}...`;
    sendBtn.disabled = !chatInput.value.trim();
}

function setCompanyContext(company, renderWelcome = true) {
    activeCompany = company;
    
    // Update sidebar highlights
    document.querySelectorAll('.company-item').forEach(el => {
        if (company === null) {
            el.classList.toggle('active', !el.dataset.name);
        } else {
            el.classList.toggle('active', el.dataset.name === company);
        }
    });

    if (company) {
        activeCompanyBadge.textContent = company;
        activeCompanyBadge.parentElement.style.display = 'flex';
        resetContextBtn.style.display = 'block';
    } else {
        activeCompanyBadge.textContent = 'All Companies';
        resetContextBtn.style.display = 'none';
    }
    
    // Enable the input fields
    enableChatInput();

    if (renderWelcome) {
        companyPickerContainer.style.display = 'none';
        welcomeContainer.style.display = 'flex';
        messagesContainer.style.display = 'none';
        generateSuggestedQuestions();
    }
    
    if (window.innerWidth <= 768) {
        sidebar.classList.remove('active');
    }
}

function filterCompanies(query) {
    const term = query.toLowerCase();
    document.querySelectorAll('.company-list .company-item').forEach(el => {
        const name = el.dataset.name;
        if (!name) return; // Keep "All Companies"
        if (name.toLowerCase().includes(term)) {
            el.style.display = 'flex';
        } else {
            el.style.display = 'none';
        }
    });
}

// ── Generate Suggested Questions ──
function generateSuggestedQuestions() {
    suggestedGrid.innerHTML = '';
    const company = activeCompany || (companiesList.length > 0 ? companiesList[0] : 'Zoho');
    
    const sampleQs = [
        `What rounds does ${company} have?`,
        `What salary does ${company} offer?`,
        `What coding questions were asked in ${company}?`,
        `Give me preparation tips for ${company}`
    ];

    sampleQs.forEach(q => {
        const card = document.createElement('button');
        card.className = 'suggested-card';
        card.textContent = q;
        card.addEventListener('click', () => {
            chatInput.value = q;
            chatInput.style.height = 'auto';
            chatInput.style.height = (chatInput.scrollHeight) + 'px';
            sendBtn.disabled = false;
            sendMessage();
        });
        suggestedGrid.appendChild(card);
    });
}

// ── Render Message Bubbles ──
function appendMessageBubble(role, content, companyContext = null) {
    const bubbleWrapper = document.createElement('div');
    bubbleWrapper.className = `message-wrapper ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    if (role === 'assistant') {
        bubble.innerHTML = marked.parse(content);
        
        // Post-process external links to display as clean buttons
        const links = bubble.querySelectorAll('a');
        links.forEach(link => {
            const href = link.getAttribute('href');
            if (href && (href.startsWith('http://') || href.startsWith('https://'))) {
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                
                let label = 'Link to Question';
                try {
                    const urlObj = new URL(href);
                    const host = urlObj.hostname.replace('www.', '');
                    if (host.includes('leetcode')) label = 'LeetCode';
                    else if (host.includes('geeksforgeeks')) label = 'GeeksforGeeks';
                    else if (host.includes('hackerrank')) label = 'HackerRank';
                    else if (host.includes('github')) label = 'GitHub';
                    else if (host.includes('ambitionbox')) label = 'AmbitionBox';
                    else if (host.includes('glassdoor')) label = 'Glassdoor';
                } catch(e) {}
                
                link.innerHTML = `🌐 ${label}`;
                link.classList.add('external-link-btn');
            }
        });

        // Add copy button
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'message-actions';
        
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.innerHTML = `
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            Copy
        `;
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(content).then(() => {
                copyBtn.innerHTML = `
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                    Copied!
                `;
                setTimeout(() => {
                    copyBtn.innerHTML = `
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                        Copy
                    `;
                }, 2000);
            });
        });
        actionsDiv.appendChild(copyBtn);

        // Add Web Search Button if there is an active company
        if (activeCompany) {
            const checkWebBtn = document.createElement('button');
            checkWebBtn.className = 'copy-btn web-search-bubble-btn';
            checkWebBtn.innerHTML = `
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                🌐 Check Web Feedback
            `;
            checkWebBtn.addEventListener('click', async () => {
                checkWebBtn.disabled = true;
                const origText = checkWebBtn.innerHTML;
                checkWebBtn.innerHTML = `
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px; display: inline-block; animation: spin 1s linear infinite;"><circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.2)" stroke-dasharray="16" /><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" /></svg>
                    Searching...
                `;
                
                showToast(`Searching web for ${activeCompany} feedback...`);
                try {
                    const serperKey = serperApiKeyInput.value.trim() || llmSettings.serper_api_key;
                    const res = await apiFetch('/api/scrape', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            company: activeCompany,
                            serper_api_key: serperKey || null
                        })
                    });
                    const data = await res.json();
                    
                    if (res.status === 200) {
                        showToast(`Successfully indexed web feedback for ${activeCompany}!`);
                        
                        chatInput.value = `Summarize the web feedback (Glassdoor, AmbitionBox, GeeksforGeeks) for ${activeCompany}`;
                        chatInput.style.height = 'auto';
                        chatInput.style.height = (chatInput.scrollHeight) + 'px';
                        sendBtn.disabled = false;
                        sendMessage();
                    } else {
                        throw new Error(data.detail || 'Failed to scrape');
                    }
                } catch (e) {
                    alert(`Search error: ${e.message}`);
                } finally {
                    checkWebBtn.disabled = false;
                    checkWebBtn.innerHTML = origText;
                }
            });
            actionsDiv.appendChild(checkWebBtn);
        }

        bubble.appendChild(actionsDiv);
    } else {
        bubble.textContent = content;
        
        if (companyContext) {
            const contextTag = document.createElement('span');
            contextTag.style.display = 'block';
            contextTag.style.fontSize = '0.75rem';
            contextTag.style.color = 'rgba(255,255,255,0.7)';
            contextTag.style.marginTop = '4px';
            contextTag.style.fontStyle = 'italic';
            contextTag.textContent = `Target: ${companyContext}`;
            bubble.appendChild(contextTag);
        }
    }

    bubbleWrapper.appendChild(bubble);
    messagesContainer.appendChild(bubbleWrapper);
}

function showTypingIndicator() {
    const bubbleWrapper = document.createElement('div');
    bubbleWrapper.className = 'message-wrapper assistant typing-indicator-wrapper';

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    
    bubble.innerHTML = `
        <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    `;

    bubbleWrapper.appendChild(bubble);
    messagesContainer.appendChild(bubbleWrapper);
    scrollToBottom();
}

function removeTypingIndicator() {
    const indicator = document.querySelector('.typing-indicator-wrapper');
    if (indicator) {
        indicator.remove();
    }
}

// ── Sending Message ──
async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text || activeCompany === null) return;

    if (!activeSessionId) {
        await createNewSession();
    }

    // Hide empty state
    welcomeContainer.style.display = 'none';
    messagesContainer.style.display = 'flex';

    // Append user message
    appendMessageBubble('user', text, activeCompany);
    
    chatInput.value = '';
    chatInput.style.height = 'auto';
    sendBtn.disabled = true;
    scrollToBottom();

    // Show typing loader
    showTypingIndicator();

    try {
        const payload = {
            question: text,
            company: activeCompany,
            session_id: activeSessionId,
            settings: (llmSettings.api_key || llmSettings.api_url) ? llmSettings : null
        };

        const res = await apiFetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        removeTypingIndicator();

        if (data.answer) {
            appendMessageBubble('assistant', data.answer);
            
            const session = sessionsList.find(s => s.id === activeSessionId);
            if (session && session.title !== data.session_title) {
                session.title = data.session_title;
                renderSessions();
            }
        } else {
            appendMessageBubble('assistant', '⚠️ Received an empty response. Please check backend connection.');
        }
    } catch (e) {
        removeTypingIndicator();
        appendMessageBubble('assistant', `⚠️ Error calling API: ${e.message}`);
    }
    scrollToBottom();
}

// ── Upload Handlers ──
function renderSelectedFiles() {
    selectedFilesList.innerHTML = '';
    const files = fileInput.files;
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const row = document.createElement('div');
        row.className = 'file-row';
        row.innerHTML = `
            <span>${escapeHtml(file.name)}</span>
            <span>${(file.size / 1024).toFixed(1)} KB</span>
        `;
        selectedFilesList.appendChild(row);
    }
}

async function handleUpload() {
    const companySelectVal = uploadCompanySelect.value;
    const companyInputVal = uploadCompanyInput.value.trim();
    const company = companyInputVal || companySelectVal;

    if (!company) {
        alert('Please select or type a company name');
        return;
    }

    const files = fileInput.files;
    if (files.length === 0) {
        alert('Please select at least one file to upload');
        return;
    }

    const formData = new FormData();
    formData.append('company', company);
    for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i]);
    }

    uploadProgressContainer.style.display = 'block';
    uploadProgressBar.style.width = '10%';
    uploadStatusText.textContent = 'Uploading files to server...';
    startUploadBtn.disabled = true;

    try {
        const token = localStorage.getItem('auth_token');
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/upload', true);
        if (token) {
            xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        }

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 80) + 10;
                uploadProgressBar.style.width = `${percent}%`;
            }
        };

        xhr.onload = async () => {
            if (xhr.status === 200) {
                uploadProgressBar.style.width = '100%';
                uploadStatusText.textContent = 'Re-indexed and saved successfully!';
                
                await loadCompanies();
                
                setTimeout(() => {
                    uploadModal.classList.remove('active');
                    startUploadBtn.disabled = false;
                    showToast(`Successfully uploaded ${files.length} document(s) for ${company}!`);
                }, 1000);
            } else if (xhr.status === 401) {
                logout();
                uploadModal.classList.remove('active');
                startUploadBtn.disabled = false;
            } else {
                throw new Error(xhr.responseText || 'Upload failed');
            }
        };

        xhr.onerror = () => {
            throw new Error('Network error during upload');
        };

        xhr.send(formData);

    } catch (e) {
        uploadProgressContainer.style.display = 'none';
        uploadStatusText.textContent = `Error: ${e.message}`;
        startUploadBtn.disabled = false;
    }
}

// ── UTILITIES ──
function scrollToBottom() {
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.textContent = message;
    
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 500);
    }, 3000);
}

// ── Web Scraper Trigger (from Sidebar) ──
async function triggerCompanyScrape(company, button) {
    button.disabled = true;
    const originalHTML = button.innerHTML;
    button.innerHTML = `
        <svg class="animate-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 1s linear infinite;"><circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.2)" stroke-dasharray="16" /><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" /></svg>
    `;
    
    showToast(`Scraping web feedback for ${company}...`);
    try {
        const serperKey = serperApiKeyInput.value.trim() || llmSettings.serper_api_key;
        const res = await apiFetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                company: company,
                serper_api_key: serperKey || null
            })
        });
        const data = await res.json();
        
        if (res.status === 200) {
            showToast(`Successfully indexed web feedback for ${company}!`);
            setCompanyContext(company);
            
            chatInput.value = `Summarize the web feedback (Glassdoor, AmbitionBox, GeeksforGeeks) for ${company}`;
            chatInput.style.height = 'auto';
            chatInput.style.height = (chatInput.scrollHeight) + 'px';
            sendBtn.disabled = false;
            sendMessage();
        } else {
            throw new Error(data.detail || 'Failed to scrape');
        }
    } catch (e) {
        alert(`Scraping error: ${e.message}`);
    } finally {
        button.disabled = false;
        button.innerHTML = originalHTML;
    }
}
