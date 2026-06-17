/**
 * BM25S Retriever UI JavaScript
 */

// Global state
let currentDocuments = [];
let currentSettings = {};
let hybridCapability = {};

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    initTabs();
    initSearchTab();
    initDocumentsTab();
    initSettingsTab();
    initStatusTab();
    loadInitialData();
});

// Tab functionality
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanels = document.querySelectorAll('[data-tab-panel]');
    
    // Function to switch to a specific tab
    function switchToTab(targetTab) {
        // Update button states
        tabButtons.forEach(btn => btn.classList.remove('active'));
        const activeButton = document.querySelector(`[data-tab-target="${targetTab}"]`);
        if (activeButton) {
            activeButton.classList.add('active');
        }
        
        // Update panel visibility
        tabPanels.forEach(panel => {
            if (panel.dataset.tabPanel === targetTab) {
                panel.classList.remove('panel-hidden');
            } else {
                panel.classList.add('panel-hidden');
            }
        });
        
        // Update URL hash
        window.location.hash = targetTab;
    }
    
    // Add click listeners to tab buttons
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetTab = button.dataset.tabTarget;
            switchToTab(targetTab);

            // Load data when switching to specific tabs
            if (targetTab === 'mcp-providers') {
                loadMCPProviders();
            } else if (targetTab === 'tool-management') {
                loadDocuments();
            }
        });
    });
    
    // Handle URL hash changes
    function handleHashChange() {
        const hash = window.location.hash.slice(1); // Remove #
        if (hash && document.querySelector(`[data-tab-panel="${hash}"]`)) {
            switchToTab(hash);
        } else if (!hash) {
            // Default to first tab if no hash
            const firstTab = document.querySelector('.tab-button');
            if (firstTab) {
                switchToTab(firstTab.dataset.tabTarget);
            }
        }
    }
    
    // Listen for hash changes
    window.addEventListener('hashchange', handleHashChange);
    
    // Handle initial hash on page load
    handleHashChange();
}

// Search tab functionality
function initSearchTab() {
    const searchBtn = document.getElementById('search-btn');
    const clearBtn = document.getElementById('search-clear');
    const temperatureInput = document.getElementById('search-temperature');
    const cutoffInput = document.getElementById('search-cutoff');
    
    searchBtn?.addEventListener('click', performSearch);
    clearBtn?.addEventListener('click', clearSearch);
    document.getElementById('search-hybrid')?.addEventListener(
        'change',
        updateHybridSearchControls
    );
    temperatureInput?.addEventListener('input', updateSearchSliderLabels);
    cutoffInput?.addEventListener('input', updateSearchSliderLabels);
    updateSearchSliderLabels();
    
    // Add enter key support for search query
    document.getElementById('search-query')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            performSearch();
        }
    });
}

function updateSearchSliderLabels() {
    const temperatureInput = document.getElementById('search-temperature');
    const temperatureValue = document.getElementById('search-temperature-value');
    const cutoffInput = document.getElementById('search-cutoff');
    const cutoffValue = document.getElementById('search-cutoff-value');

    if (temperatureInput && temperatureValue) {
        temperatureValue.textContent = Number.parseFloat(temperatureInput.value).toFixed(1);
    }
    if (cutoffInput && cutoffValue) {
        cutoffValue.textContent = `${Number.parseFloat(cutoffInput.value).toFixed(1).replace(/\.0$/, '')}%`;
    }
}

async function performSearch() {
    const query = document.getElementById('search-query').value.trim();
    if (!query) {
        showMessage('search-results', 'Please enter a search query', 'error');
        return;
    }
    
    const temperature = parseFloat(document.getElementById('search-temperature').value);
    const cutoffInput = document.getElementById('search-cutoff').value;
    const cutoff = cutoffInput === '' ? 0.0 : parseFloat(cutoffInput);
    
    // Update UI to show 0 if user cleared the field
    if (cutoffInput === '') {
        document.getElementById('search-cutoff').value = '0.0';
    }
    const ignoreZero = document.getElementById('search-ignore-zero').checked;
    const hybridSearch = document.getElementById('search-hybrid').checked;
    const maxTools = parseInt(document.getElementById('search-max-tools').value, 10);
    const minRrfScoreInput = document.getElementById('search-min-rrf-score').value;
    const minRrfScore = minRrfScoreInput === ''
        ? null
        : parseFloat(minRrfScoreInput);
    if (!Number.isInteger(maxTools) || maxTools < 1 || maxTools > 100) {
        showMessage('search-results', 'Max Tools must be between 1 and 100', 'error');
        return;
    }
    if (minRrfScore !== null && (!Number.isFinite(minRrfScore) || minRrfScore < 0)) {
        showMessage('search-results', 'Minimum RRF Score must be 0 or greater', 'error');
        return;
    }
    
    try {
        showMessage('search-results', 'Searching...', 'info');
        
        if (hybridSearch) {
            const response = await fetch('/retrieve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    hybrid_search: true,
                    max_results: maxTools,
                    ...(minRrfScore !== null && { min_rrf_score: minRrfScore })
                })
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || data.message || 'Hybrid search failed');
            }
            displayHybridSearchResults(data);
            return;
        }

        // Lexical mode compares softmax at temperature 1.0 and the selected value.
        const [response1, response2] = await Promise.all([
            fetch('/retrieve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    temperature: 1.0,
                    llm_tools_cutoff: cutoff,
                    ignore_zero: ignoreZero,
                    max_results: maxTools
                })
            }),
            fetch('/retrieve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    temperature,
                    llm_tools_cutoff: cutoff,
                    ignore_zero: ignoreZero,
                    max_results: maxTools
                })
            })
        ]);
        
        const data1 = await response1.json();
        const data2 = await response2.json();
        
        if (!response1.ok) {
            throw new Error(data1.detail || data1.message || 'Search failed');
        }
        if (!response2.ok) {
            throw new Error(data2.detail || data2.message || 'Search failed');
        }
        
        displaySearchResults(data1, data2);
        
    } catch (error) {
        showMessage('search-results', `Error: ${error.message}`, 'error');
    }
}

function displaySearchResults(dataTemp1, dataUserTemp) {
    const resultsDiv = document.getElementById('search-results');
    
    if (!dataUserTemp.documents || dataUserTemp.documents.length === 0) {
        showMessage('search-results', 'No documents found matching your query', 'warning');
        return;
    }
    
    // Get the user temperature from the input field
    const userTemp = parseFloat(document.getElementById('search-temperature').value);
    
    // Create a map of document IDs to their temp 1.0 scores
    const temp1Scores = {};
    dataTemp1.documents.forEach(doc => {
        temp1Scores[doc.id] = doc.softmax_score;
    });
    
    let html = `
        <div class="muted" style="margin-bottom: 12px;">
            Found ${dataUserTemp.documents.length} documents (from ${dataUserTemp.total_retrieved} total)
        </div>
        <div class="search-results-list">
    `;
    
    dataUserTemp.documents.forEach(doc => {
        const temp1Score = temp1Scores[doc.id] || 0;
        const temp1Percent = (temp1Score * 100).toFixed(2);
        const userTempPercent = (doc.softmax_score * 100).toFixed(2);
        const bm25Score = doc.bm25_score.toFixed(3);
        
        html += `
            <div class="search-result-card">
                <div class="search-result-header">
                    <div class="search-result-info">
                        <div class="search-result-id">${escapeHtml(doc.id)}</div>
                        <div class="search-result-description" onclick="this.classList.toggle('expanded')">${escapeHtml(doc.content)}</div>
                    </div>
                </div>
                <div class="search-result-metrics">
                    <div class="search-result-metric">
                        <span class="search-result-metric-label">BM25 Score</span>
                        <span class="search-result-metric-value">${bm25Score}</span>
                    </div>
                    <div class="search-result-metric">
                        <span class="search-result-metric-label">Softmax @ 1.0</span>
                        <span class="search-result-metric-value">${temp1Percent}%</span>
                    </div>
                    <div class="search-result-metric">
                        <span class="search-result-metric-label">Softmax @ ${userTemp}</span>
                        <span class="search-result-metric-value highlight">${userTempPercent}%</span>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += `
        </div>
    `;
    
    resultsDiv.innerHTML = html;
}

function displayHybridSearchResults(data) {
    const resultsDiv = document.getElementById('search-results');
    if (!data.documents || data.documents.length === 0) {
        showMessage('search-results', 'No documents found matching your query', 'warning');
        return;
    }

    let html = `
        <div class="muted" style="margin-bottom: 12px;">
            Found ${data.documents.length} documents using BM25 + ColBERT reciprocal rank fusion.
        </div>
        <div class="search-results-list">
    `;

    data.documents.forEach(doc => {
        const bm25Score = doc.bm25_score !== null && doc.bm25_score !== undefined ? doc.bm25_score.toFixed(3) : null;
        const colbertScore = doc.colbert_score !== null && doc.colbert_score !== undefined ? doc.colbert_score.toFixed(3) : null;
        
        html += `
            <div class="search-result-card">
                <div class="search-result-header">
                    <div class="search-result-info">
                        <div class="search-result-id">${escapeHtml(doc.id)}</div>
                        <div class="search-result-description" onclick="this.classList.toggle('expanded')">${escapeHtml(doc.content)}</div>
                    </div>
                </div>
                <div class="search-result-metrics">
                    <div class="search-result-metric">
                        <span class="search-result-metric-label">BM25 Rank</span>
                        <span class="search-result-metric-value">${formatRank(doc.bm25_rank)}${bm25Score ? ` (Score: ${bm25Score})` : ''}</span>
                    </div>
                    <div class="search-result-metric">
                        <span class="search-result-metric-label">ColBERT Rank</span>
                        <span class="search-result-metric-value">${formatRank(doc.colbert_rank)}${colbertScore ? ` (Score: ${colbertScore})` : ''}</span>
                    </div>
                    <div class="search-result-metric">
                        <span class="search-result-metric-label">RRF Score</span>
                        <span class="search-result-metric-value highlight">${doc.rrf_score.toFixed(6)}</span>
                    </div>
                </div>
            </div>
        `;
    });

    html += `
        </div>
    `;

    resultsDiv.innerHTML = html;
}

function formatRank(rank) {
    return rank === null || rank === undefined ? '-' : rank;
}

function updateHybridSearchControls() {
    const checked = document.getElementById('search-hybrid').checked;
    ['search-temperature', 'search-cutoff', 'search-ignore-zero'].forEach(id => {
        document.getElementById(id).disabled = checked;
    });
    document.getElementById('search-min-rrf-score').disabled = !checked;
}

function clearSearch() {
    document.getElementById('search-query').value = '';
    document.getElementById('search-results').innerHTML = '<div class="muted">Enter a query to search documents.</div>';
}

// Documents tab functionality
function initDocumentsTab() {
    const addBtn = document.getElementById('add-document-btn');
    const reindexBtn = document.getElementById('reindex-bm25s-btn');
    const reloadBtn = document.getElementById('reload-index-btn');
    const saveBtn = document.getElementById('save-document-btn');
    const fileSelector = document.getElementById('file-selector');
    const switchFileBtn = document.getElementById('switch-file-btn');
    
    addBtn?.addEventListener('click', () => {
        document.getElementById('add-document-modal').style.display = 'block';
    });
    
    reindexBtn?.addEventListener('click', reindexBm25s);
    reloadBtn?.addEventListener('click', reloadIndex);
    saveBtn?.addEventListener('click', saveDocument);
    
    // File selector functionality
    fileSelector?.addEventListener('change', () => {
        const selectedFile = fileSelector.value;
        switchFileBtn.disabled = !selectedFile || selectedFile === getCurrentFile();
    });
    
    switchFileBtn?.addEventListener('click', switchDocumentFile);
    
    // Filter toggle functionality
    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadDocuments();
        });
    });
    
    // Modal can only be closed by X button (no outside-click closing)
}

function closeModal() {
    document.getElementById('add-document-modal').style.display = 'none';
    clearDocumentForm();
}

function clearDocumentForm() {
    document.getElementById('doc-id').value = '';
    document.getElementById('doc-title').value = '';
    document.getElementById('doc-content').value = '';
    document.getElementById('doc-keywords').value = '';
}

async function saveDocument() {
    const id = document.getElementById('doc-id').value.trim();
    const title = document.getElementById('doc-title').value.trim();
    const content = document.getElementById('doc-content').value.trim();
    const keywordsStr = document.getElementById('doc-keywords').value.trim();
    
    if (!id || !title || !content) {
        alert('Please fill in ID, title, and content fields');
        return;
    }
    
    const keywords = keywordsStr ? keywordsStr.split(',').map(k => k.trim()).filter(k => k) : [];
    
    try {
        const response = await fetch('/index', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                documents: [{
                    id,
                    title,
                    content,
                    keywords,
                    metadata: {
                        source: 'ui',
                        added_at: new Date().toISOString()
                    }
                }],
                rebuild: false
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Failed to save document');
        }
        
        showMessage('documents-result', 'Document added successfully', 'success');
        closeModal();
        loadDocuments();
        
    } catch (error) {
        showMessage('documents-result', `Error: ${error.message}`, 'error');
    }
}

async function loadDocuments() {
    try {
        const response = await fetch('/documents');
        const data = await response.json();
        
        if (response.ok) {
            displayDocuments(data.documents || []);
            if (data.warning) {
                showMessage('documents-result', data.warning, 'warning');
            }
        }
    } catch (error) {
        console.error('Failed to load documents:', error);
    }
}

function displayDocuments(documents) {
    const toolsList = document.getElementById('tools-list');
    const noDocsMsg = document.getElementById('no-documents-message');
    const totalCount = document.getElementById('total-indexed');
    const localCount = document.getElementById('local-tools-count');
    const mcpCount = document.getElementById('mcp-tools-count');
    
    // Count by type
    const localDocs = documents.filter(doc => doc.type === 'local');
    const mcpDocs = documents.filter(doc => doc.type === 'mcp');
    
    // Update metric cards
    totalCount.textContent = documents.length;
    localCount.textContent = localDocs.length;
    mcpCount.textContent = mcpDocs.length;
    
    // Get current filter
    const activeFilter = document.querySelector('.filter-btn.active')?.dataset.filter || 'all';
    
    // Filter documents
    let filteredDocs = documents;
    if (activeFilter === 'local') {
        filteredDocs = localDocs;
    } else if (activeFilter === 'mcp') {
        filteredDocs = mcpDocs;
    }
    
    // Update tools list
    if (filteredDocs.length === 0) {
        toolsList.style.display = 'none';
        noDocsMsg.style.display = 'block';
    } else {
        toolsList.style.display = 'flex';
        noDocsMsg.style.display = 'none';
        
        // Sort documents: local first, then MCP
        const sortedDocuments = [...filteredDocs].sort((a, b) => {
            if (a.type === 'local' && b.type === 'mcp') return -1;
            if (a.type === 'mcp' && b.type === 'local') return 1;
            return 0;
        });

        toolsList.innerHTML = sortedDocuments.map(doc => {
            const isMCP = doc.type === 'mcp';
            const isLocal = doc.type === 'local';
            
            const sourcePill = isMCP ? 
                '<span class="source-pill mcp">MCP</span>' :
                '<span class="source-pill local">Local</span>';
            
            const categoryTag = doc.category ? 
                `<span class="category-tag">${escapeHtml(doc.category)}</span>` : '';
            
            return `
                <div class="tool-row-card">
                    ${sourcePill}
                    <div class="tool-main">
                        <div class="tool-title-row">
                            <span class="tool-title">${escapeHtml(doc.title)}</span>
                            <span class="tool-id">${escapeHtml(doc.id)}</span>
                        </div>
                        <div class="tool-description">${escapeHtml(doc.description || '')}</div>
                        <div class="tool-meta">
                            ${categoryTag}
                        </div>
                    </div>
                    <div class="tool-actions">
                        <span style="color: #999; font-size: 12px;" title="Documents from cache cannot be deleted via UI">-</span>
                    </div>
                </div>
            `;
        }).join('');
    }
}

async function deleteDocument(documentId) {
    if (!confirm(`Are you sure you want to delete document "${documentId}"?`)) {
        return;
    }
    
    try {
        showMessage('documents-result', 'Deleting document...', 'info');
        
        const response = await fetch(`/documents/${encodeURIComponent(documentId)}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Failed to delete document');
        }
        
        showMessage('documents-result', 'Document deleted successfully', 'success');
        loadDocuments();
        
    } catch (error) {
        showMessage('documents-result', `Error: ${error.message}`, 'error');
    }
}

async function reloadIndex() {
    if (!confirm('This will delete all documents manually passed via UI and reload from YAML file. Are you sure you want to continue?')) {
        return;
    }
    
    try {
        showMessage('documents-result', 'Reloading index...', 'info');
        
        const response = await fetch('/documents/reload', { method: 'POST' });
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Failed to reload index');
        }
        
        showMessage('documents-result', 'Index reloaded successfully', 'success');
        loadDocuments();
        
    } catch (error) {
        showMessage('documents-result', `Error: ${error.message}`, 'error');
    }
}

async function reindexBm25s() {
    try {
        showMessage('documents-result', 'Reindexing retrieval indexes...', 'info');
        
        const response = await fetch('/documents/reindex-bm25s', { method: 'POST' });
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Failed to reindex retrieval');
        }
        
        const indexTime = data.index_time_ms !== undefined ? ` in ${data.index_time_ms.toFixed(2)}ms` : '';
        showMessage('documents-result', `${data.message || 'Retrieval indexes rebuilt successfully'}${indexTime}`, 'success');
        loadDocuments();
        
    } catch (error) {
        showMessage('documents-result', `Error: ${error.message}`, 'error');
    }
}

// Settings tab functionality
function initSettingsTab() {
    const saveBtn = document.getElementById('settings-save');
    saveBtn?.addEventListener('click', saveSettings);
}

async function loadSettings() {
    try {
        const response = await fetch('/settings');
        const data = await response.json();
        
        if (response.ok) {
            currentSettings = data;
            updateSettingsUI(data);
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

function updateSettingsUI(settings) {
    document.getElementById('settings-temperature').value = settings.bm25s.temperature;
    document.getElementById('settings-ignore-zero').checked = settings.bm25s.ignore_zero;
    document.getElementById('settings-cutoff').value = settings.bm25s.llm_tools_cutoff;
    updateHybridCapability(settings.hybrid_search || {});
    
    // Also update search tab defaults
    updateSearchTabDefaults(settings);
}

function updateHybridCapability(capability) {
    hybridCapability = capability;
    const checkbox = document.getElementById('search-hybrid');
    const status = document.getElementById('search-hybrid-status');
    const available = Boolean(capability.available);
    checkbox.disabled = !available;
    if (!available) {
        checkbox.checked = false;
    }
    if (!capability.enabled) {
        status.textContent = 'Disabled by server configuration. Set AXIOLEX_HYBRID_ENABLED=true and install axiolex[colbert].';
    } else if (capability.error) {
        status.textContent = capability.error;
    } else {
        status.innerHTML = '<strong>*</strong> Hybrid available using late interaction colbert-ir/colbertv2.0 with ONNX.';
    }
    updateHybridSearchControls();
}

function updateSearchTabDefaults(settings) {
    document.getElementById('search-temperature').value = settings.bm25s.temperature;
    document.getElementById('search-ignore-zero').checked = settings.bm25s.ignore_zero;
    document.getElementById('search-cutoff').value = settings.bm25s.llm_tools_cutoff;
    updateSearchSliderLabels();
}

async function saveSettings() {
    const temperature = parseFloat(document.getElementById('settings-temperature').value);
    const ignoreZero = document.getElementById('settings-ignore-zero').checked;
    const cutoffInput = document.getElementById('settings-cutoff').value;
    const cutoff = cutoffInput === '' ? 0.0 : parseFloat(cutoffInput);
    
    // Update UI to show 0 if user cleared the field
    if (cutoffInput === '') {
        document.getElementById('settings-cutoff').value = '0.0';
    }
    
    try {
        showMessage('settings-result', 'Saving settings...', 'info');
        
        const response = await fetch('/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                temperature,
                ignore_zero: ignoreZero,
                llm_tools_cutoff: cutoff
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Failed to save settings');
        }
        
        showMessage('settings-result', 'Settings saved successfully', 'success');
        updateSettingsUI(data);
        
    } catch (error) {
        showMessage('settings-result', `Error: ${error.message}`, 'error');
    }
}

// Status tab functionality
function initStatusTab() {
    const refreshBtn = document.getElementById('status-refresh');
    refreshBtn?.addEventListener('click', reloadService);
}

async function reloadService() {
    if (!confirm('This restarts the BM25S retriever service. All in-memory documents will be lost. Are you sure you want to continue?')) {
        return;
    }
    
    try {
        document.getElementById('service-status').innerHTML = '<div class="muted">Restarting service...</div>';
        
        const response = await fetch('/reload', { method: 'POST' });
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Failed to restart service');
        }
        
        // Reload status after restart
        await loadStatus();
        
    } catch (error) {
        document.getElementById('service-status').innerHTML = 
            `<div class="muted" style="color: red;">Error restarting service: ${error.message}</div>`;
    }
}

async function loadStatus() {
    try {
        const response = await fetch('/status');
        const data = await response.json();
        
        if (response.ok) {
            displayStatus(data);
        }
    } catch (error) {
        document.getElementById('service-status').innerHTML = 
            `<div class="muted" style="color: red;">Error loading status: ${error.message}</div>`;
    }
}

function displayStatus(data) {
    const statusDiv = document.getElementById('service-status');
    const metricsDiv = document.getElementById('performance-metrics');
    
    statusDiv.innerHTML = `
        <div style="display: grid; gap: 8px;">
            <div><strong>Status:</strong> <span style="color: ${data.status === 'healthy' ? 'green' : 'red'};">${data.status}</span></div>
            <div><strong>Document Count:</strong> ${data.document_count}</div>
            <div><strong>Retriever Initialized:</strong> ${data.retriever_initialized ? 'Yes' : 'No'}</div>
            <div><strong>Version:</strong> ${data.version}</div>
            <div><strong>Hybrid Search:</strong> ${data.hybrid_search?.available ? `Available (${escapeHtml(data.hybrid_search.model)})` : 'Unavailable'}</div>
        </div>
    `;
    
    metricsDiv.innerHTML = `
        <div class="muted">
            <p>Performance metrics will be available after search operations.</p>
            <p>Monitor search response times and result quality.</p>
        </div>
    `;
}

// Utility functions
function showMessage(elementId, message, type = 'info') {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    // Special handling for success-banner format
    if (elementId === 'documents-result') {
        let textSpan = document.getElementById('documents-result-text');
        if (!textSpan) {
            // Recreate the span if it was destroyed
            element.innerHTML = '<span id="documents-result-text"></span>';
            textSpan = document.getElementById('documents-result-text');
        }
        if (textSpan) {
            textSpan.textContent = message;
        }
        if (type === 'success') {
            element.classList.remove('hidden');
            element.style.color = '';
        } else {
            element.classList.remove('hidden');
            element.style.color = type === 'error' ? 'red' : type === 'warning' ? 'orange' : '#666';
        }
        return;
    }
    
    // Special handling for providers-result success-banner format
    if (elementId === 'providers-result') {
        const textSpan = document.getElementById('providers-result-text');
        if (textSpan) {
            textSpan.textContent = message;
        }
        if (type === 'success') {
            element.classList.remove('hidden');
        } else {
            element.classList.add('hidden');
            // For non-success messages, show inline
            element.innerHTML = `<div style="color: ${type === 'error' ? 'red' : type === 'warning' ? 'orange' : '#666'};">${message}</div>`;
            element.classList.remove('hidden');
        }
        return;
    }
    
    // Special handling for settings-result success-banner format
    if (elementId === 'settings-result') {
        const textSpan = document.getElementById('settings-result-text');
        if (textSpan) {
            textSpan.textContent = message;
        }
        if (type === 'success') {
            element.classList.remove('hidden');
        } else {
            element.classList.add('hidden');
            // For non-success messages, show inline
            element.innerHTML = `<div style="color: ${type === 'error' ? 'red' : type === 'warning' ? 'orange' : '#666'};">${message}</div>`;
            element.classList.remove('hidden');
        }
        return;
    }
    
    const colors = {
        info: '#666',
        success: 'green',
        warning: 'orange',
        error: 'red'
    };
    
    element.innerHTML = `<div style="color: ${colors[type]};">${message}</div>`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadDocumentFiles() {
    try {
        const response = await fetch('/document-files');
        const data = await response.json();
        
        if (response.ok) {
            // Update current file display
            document.getElementById('current-file').textContent = data.current_file;
            
            // Update file selector
            const selector = document.getElementById('file-selector');
            selector.innerHTML = '';
            
            data.available_files.forEach(file => {
                const option = document.createElement('option');
                option.value = file;
                option.textContent = file;
                if (file === data.current_file) {
                    option.selected = true;
                }
                selector.appendChild(option);
            });
            
            // Enable/disable switch button
            const switchBtn = document.getElementById('switch-file-btn');
            switchBtn.disabled = true;
            
            return data;
        }
    } catch (error) {
        console.error('Failed to load document files:', error);
        document.getElementById('current-file').textContent = 'Error loading';
    }
}

function getCurrentFile() {
    return document.getElementById('current-file').textContent.trim();
}

async function switchDocumentFile() {
    const selector = document.getElementById('file-selector');
    const selectedFile = selector.value;
    
    if (!selectedFile || selectedFile === getCurrentFile()) {
        return;
    }
    
    try {
        // First, check if warning is needed
        const response = await fetch('/switch-document-file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: selectedFile,
                confirmed: false
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            if (data.requires_warning) {
                // Show confirmation dialog
                if (confirm(`${data.warning_message}\n\nThis action cannot be undone.\n\nContinue?`)) {
                    // User confirmed, proceed with switch
                    await performFileSwitch(selectedFile, true);
                }
            } else {
                // No warning needed, proceed directly
                await performFileSwitch(selectedFile, true);
            }
        } else {
            throw new Error(data.detail || data.message || 'Failed to switch file');
        }
    } catch (error) {
        showMessage('file-switch-result', `Error: ${error.message}`, 'error');
    }
}

async function performFileSwitch(filename, confirmed) {
    try {
        showMessage('file-switch-result', 'Switching file...', 'info');
        
        const response = await fetch('/switch-document-file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: filename,
                confirmed: confirmed
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage('file-switch-result', data.message, 'success');
            
            // Reload document files info
            await loadDocumentFiles();
            
            // Reload documents list
            await loadDocuments();
        } else {
            throw new Error(data.detail || data.message || 'Failed to switch file');
        }
    } catch (error) {
        showMessage('file-switch-result', `Error: ${error.message}`, 'error');
    }
}

// MCP Providers tab functionality
async function loadMCPProviders() {
    try {
        const response = await fetch('/mcp-providers');
        const data = await response.json();
        
        if (response.ok) {
            displayMCPProviders(data.providers || []);
        }
    } catch (error) {
        console.error('Failed to load MCP providers:', error);
    }
}

function displayMCPProviders(providers) {
    const providersList = document.getElementById('providers-list');
    const noProvidersMsg = document.getElementById('no-providers-message');
    
    if (providers.length === 0) {
        providersList.style.display = 'none';
        noProvidersMsg.style.display = 'block';
    } else {
        providersList.style.display = 'flex';
        noProvidersMsg.style.display = 'none';
        
        // Sort providers: enabled first, then by name
        const sortedProviders = [...providers].sort((a, b) => {
            // First sort by enabled status (enabled first)
            if (a.enabled && !b.enabled) return -1;
            if (!a.enabled && b.enabled) return 1;
            // Then sort by name alphabetically
            return a.name.localeCompare(b.name);
        });
        
        providersList.innerHTML = sortedProviders.map(provider => {
            const statusClass = provider.enabled ? 'enabled' : 'disabled';
            const statusText = provider.enabled ? 'Enabled' : 'Disabled';
            const endpoint = provider.transport === 'stdio' ? 
                `${provider.command} ${provider.args.join(' ')}` : 
                (provider.endpoint || '-');
            
            const inspectButton = provider.enabled
                ? `<button onclick="discoverProviderTools('${escapeHtml(provider.id)}')" type="button" class="secondary">Retrieve tools</button>`
                : `<button disabled type="button" class="secondary">Retrieve tools</button>`;
            
            const removeButton = provider.enabled
                ? `<button onclick="disableProvider('${escapeHtml(provider.id)}')" type="button" class="secondary">Remove</button>`
                : '';
            
            return `
                <div class="provider-card">
                    <div class="provider-card-header">
                        <div class="provider-info">
                            <span class="provider-health-icon">🔌</span>
                            <span class="provider-name">${escapeHtml(provider.name)}</span>
                        </div>
                        <span class="provider-status ${statusClass}">${statusText}</span>
                    </div>
                    
                    <div class="provider-meta">
                        <div class="provider-meta-item">
                            <span class="provider-meta-label">Transport</span>
                            <span class="provider-meta-value">${escapeHtml(provider.transport)}</span>
                        </div>
                        <div class="provider-meta-item">
                            <span class="provider-meta-label">Endpoint</span>
                            <span class="provider-meta-value">${escapeHtml(endpoint)}</span>
                        </div>
                        <div class="provider-meta-item">
                            <span class="provider-meta-label">API Key</span>
                            <span class="provider-meta-value">${escapeHtml(provider.auth?.secret_env || 'none')}</span>
                        </div>
                    </div>
                    
                    <div class="provider-actions">
                        <button onclick="editProvider('${escapeHtml(provider.id)}')" type="button" class="secondary">Edit</button>
                        ${inspectButton}
                        ${removeButton}
                    </div>
                </div>
            `;
        }).join('');
    }
}

async function discoverProviderTools(providerId) {
    try {
        // Show progress box
        const progressBox = document.getElementById('discovery-progress-box');
        const stepsContainer = document.getElementById('discovery-steps');
        const toolsBox = document.getElementById('discovered-tools-box');
        const toolsList = document.getElementById('discovered-tools-list');

        progressBox.classList.remove('hidden');
        toolsBox.classList.add('hidden');
        stepsContainer.innerHTML = '';

        const standardSteps = [
            { text: 'Processing...', status: 'pending' },
            { text: `Connecting to MCP Server: ${providerId}`, status: 'pending' },
            { text: 'List Tools', status: 'pending' },
            { text: 'Done', status: 'pending' }
        ];
        const alphaVantageSteps = [
            ...standardSteps.slice(0, 3),
            { text: 'Call TOOL_LIST', status: 'pending' },
            { text: 'Call TOOL_GET', status: 'pending' },
            standardSteps[3]
        ];
        const steps = providerId === 'alphavantage_finance'
            ? alphaVantageSteps
            : standardSteps;

        // Render steps
        steps.forEach((step, index) => {
            const stepDiv = document.createElement('div');
            stepDiv.id = `step-${index}`;
            stepDiv.style.padding = '4px 8px';
            stepDiv.style.borderRadius = '3px';
            stepDiv.style.fontSize = '13px';
            stepDiv.innerHTML = `<span style="opacity: 0.5;">⏳</span> ${step.text}`;
            stepsContainer.appendChild(stepDiv);
        });

        // Update step status helper
        const updateStep = (index, status, errorMessage = null) => {
            const stepDiv = document.getElementById(`step-${index}`);
            if (stepDiv) {
                if (status === 'active') {
                    stepDiv.style.background = '#e3f2fd';
                    stepDiv.innerHTML = `<span style="color: #1976d2;">▶</span> ${steps[index].text}`;
                } else if (status === 'complete') {
                    stepDiv.style.background = '#e8f5e9';
                    stepDiv.innerHTML = `<span style="color: #388e3c;">✓</span> ${steps[index].text}`;
                } else if (status === 'error') {
                    stepDiv.style.background = '#ffebee';
                    const errorMsg = errorMessage ? ` - ${errorMessage}` : '';
                    stepDiv.innerHTML = `<span style="color: #d32f2f;">✗</span> ${steps[index].text}${errorMsg}`;
                }
            }
        };

        // Step 1: Processing
        updateStep(0, 'active');
        await new Promise(r => setTimeout(r, 200));
        updateStep(0, 'complete');

        // Step 2: Connecting
        updateStep(1, 'active');

        // Call the actual discovery API
        const response = await fetch(`/mcp-providers/${providerId}/discover`);
        const data = await response.json();

        if (!response.ok) {
            updateStep(1, 'error', data.detail || data.message || 'Connection failed');
            throw new Error(data.detail || data.message || 'Failed to discover tools');
        }

        updateStep(1, 'complete');

        // Complete the provider-specific stages after discovery returns.
        for (let index = 2; index < steps.length; index++) {
            updateStep(index, 'active');
            await new Promise(r => setTimeout(r, index === steps.length - 1 ? 100 : 200));
            updateStep(index, 'complete');
        }

        // Show discovered tools in card layout
        toolsBox.classList.remove('hidden');
        toolsList.innerHTML = '';

        if (data.tools && data.tools.length > 0) {
            data.tools.forEach(tool => {
                const paramsStr = tool.params ? JSON.stringify(tool.params) : '{}';
                const toolCard = document.createElement('div');
                toolCard.className = 'tool-row-card';
                toolCard.innerHTML = `
                    <div class="tool-main">
                        <div class="tool-title-row">
                            <span class="tool-title">${escapeHtml(tool.title || tool.tool_name || '')}</span>
                        </div>
                        <div class="tool-description">${escapeHtml(tool.description || '')}</div>
                        <div class="tool-meta">
                            <span class="category-tag">${escapeHtml(tool.category || 'general')}</span>
                        </div>
                    </div>
                `;
                toolsList.appendChild(toolCard);
            });
        } else {
            const noToolsMsg = document.createElement('div');
            noToolsMsg.className = 'muted';
            noToolsMsg.textContent = 'No tools discovered';
            toolsList.appendChild(noToolsMsg);
        }

        showMessage('providers-result', `Discovered ${data.count} tools from ${providerId}`, 'success');
        console.log('Discovered tools:', data.tools);

    } catch (error) {
        showMessage('providers-result', `Error: ${error.message}`, 'error');
        // Keep progress box visible to show which step failed
    }
}

async function disableProvider(providerId) {
    const confirmed = confirm(
        `Remove provider "${providerId}"?\n\n` +
        'The provider will be disabled and all of its cached tools will be cleared. ' +
        'The provider configuration will remain listed and can be enabled again later.'
    );
    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch(`/mcp-providers/${providerId}`, { method: 'DELETE' });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Failed to disable provider');
        }

        showMessage('providers-result', data.message, 'success');
        loadMCPProviders();

    } catch (error) {
        showMessage('providers-result', `Error: ${error.message}`, 'error');
    }
}

async function editProvider(providerId) {
    try {
        const response = await fetch('/mcp-providers');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Failed to load providers');
        }

        const provider = data.providers.find(p => p.id === providerId);
        if (!provider) {
            throw new Error(`Provider ${providerId} not found`);
        }

        // Populate modal with existing data
        document.getElementById('provider-id').value = provider.id;
        document.getElementById('provider-id').disabled = true; // Prevent editing ID
        document.getElementById('provider-name').value = provider.name;
        document.getElementById('provider-transport').value = provider.transport;
        document.getElementById('provider-endpoint').value = provider.endpoint || '';
        document.getElementById('provider-command').value = provider.command || '';
        document.getElementById('provider-args').value = provider.args ? provider.args.join(', ') : '';
        document.getElementById('provider-auth-type').value = provider.auth?.type || 'none';
        document.getElementById('provider-secret-env').value = provider.auth?.secret_env || '';
        document.getElementById('provider-enabled').checked = provider.enabled;
        document.getElementById('provider-supports-streaming').checked = provider.features?.supports_streaming || false;

        // Change modal title and save button behavior
        document.querySelector('#add-provider-modal .modal-header h3').textContent = 'Edit MCP Provider';
        const saveBtn = document.getElementById('save-provider-btn');
        saveBtn.textContent = 'Update Provider';
        saveBtn.dataset.mode = 'edit';
        saveBtn.dataset.providerId = providerId;

        openProviderModal();

    } catch (error) {
        showMessage('providers-result', `Error: ${error.message}`, 'error');
    }
}

// Initialize MCP providers tab
document.addEventListener('DOMContentLoaded', function() {
    const addProviderBtn = document.getElementById('add-provider-btn');
    if (addProviderBtn) {
        addProviderBtn.addEventListener('click', function() {
            openProviderModal();
        });
    }
    
    const saveProviderBtn = document.getElementById('save-provider-btn');
    if (saveProviderBtn) {
        saveProviderBtn.addEventListener('click', function() {
            saveProvider();
        });
    }
});

function openProviderModal() {
    document.getElementById('add-provider-modal').style.display = 'block';
}

function closeProviderModal() {
    document.getElementById('add-provider-modal').style.display = 'none';
    // Clear form fields
    document.getElementById('provider-id').value = '';
    document.getElementById('provider-id').disabled = false;
    document.getElementById('provider-name').value = '';
    document.getElementById('provider-endpoint').value = '';
    document.getElementById('provider-command').value = '';
    document.getElementById('provider-args').value = '';
    document.getElementById('provider-secret-env').value = '';
    document.getElementById('provider-enabled').checked = true;
    document.getElementById('provider-supports-streaming').checked = false;

    // Reset modal title and save button
    document.querySelector('#add-provider-modal .modal-header h3').textContent = 'Add MCP Provider';
    const saveBtn = document.getElementById('save-provider-btn');
    saveBtn.textContent = 'Save Provider';
    delete saveBtn.dataset.mode;
    delete saveBtn.dataset.providerId;
}

async function saveProvider() {
    try {
        const providerId = document.getElementById('provider-id').value.trim();
        const providerName = document.getElementById('provider-name').value.trim();
        const transport = document.getElementById('provider-transport').value;
        const endpoint = document.getElementById('provider-endpoint').value.trim();
        const command = document.getElementById('provider-command').value.trim();
        const argsStr = document.getElementById('provider-args').value.trim();
        const authType = document.getElementById('provider-auth-type').value;
        const secretEnv = document.getElementById('provider-secret-env').value.trim();
        const enabled = document.getElementById('provider-enabled').checked;
        const supportsStreaming = document.getElementById('provider-supports-streaming').checked;

        if (!providerId || !providerName) {
            alert('Provider ID and Name are required');
            return;
        }

        const args = argsStr ? argsStr.split(',').map(arg => arg.trim()) : [];

        const providerData = {
            id: providerId,
            name: providerName,
            transport: transport,
            endpoint: endpoint || null,
            command: command || null,
            args: args,
            auth: {
                type: authType,
                secret_env: secretEnv || null
            },
            enabled: enabled,
            features: {
                supports_streaming: supportsStreaming
            },
            limits: {
                max_page_size: 50,
                max_requests_per_minute: 60,
                max_results: 100,
                timeout_seconds: 10
            }
        };

        const saveBtn = document.getElementById('save-provider-btn');
        const isEdit = saveBtn.dataset.mode === 'edit';
        const editProviderId = saveBtn.dataset.providerId;

        showMessage('providers-result', isEdit ? 'Updating provider...' : 'Saving provider...', 'info');

        let response;
        if (isEdit) {
            response = await fetch(`/mcp-providers/${editProviderId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(providerData)
            });
        } else {
            response = await fetch('/mcp-providers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(providerData)
            });
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Failed to save provider');
        }

        showMessage('providers-result', data.message, 'success');
        closeProviderModal();
        loadMCPProviders();

    } catch (error) {
        showMessage('providers-result', `Error: ${error.message}`, 'error');
    }
}

async function loadInitialData() {
    await Promise.all([
        loadSettings(),
        loadDocuments(),
        loadStatus(),
        loadDocumentFiles(),
        loadMCPProviders()
    ]);
}
