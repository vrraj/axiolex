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
    
    searchBtn?.addEventListener('click', performSearch);
    clearBtn?.addEventListener('click', clearSearch);
    document.getElementById('search-hybrid')?.addEventListener(
        'change',
        updateHybridSearchControls
    );
    
    // Add enter key support for search query
    document.getElementById('search-query')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            performSearch();
        }
    });
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
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
                <thead>
                    <tr style="background: #f5f5f5;">
                        <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Tool ID</th>
                        <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Title</th>
                        <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Content</th>
                        <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">BM25 Score</th>
                        <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">Softmax @ Temp 1.0</th>
                        <th style="padding: 8px; text-align: center; border: 1px solid #ddd;">Softmax @ Temp ${userTemp}</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    dataUserTemp.documents.forEach(doc => {
        const temp1Score = temp1Scores[doc.id] || 0;
        const temp1Percent = (temp1Score * 100).toFixed(2);
        const userTempPercent = (doc.softmax_score * 100).toFixed(2);
        const bm25Score = doc.bm25_score.toFixed(3);
        
        html += `
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; max-width: 120px; word-wrap: break-word;">${escapeHtml(doc.id)}</td>
                <td style="padding: 8px; border: 1px solid #ddd; max-width: 150px; word-wrap: break-word;">${escapeHtml(doc.title)}</td>
                <td style="padding: 8px; border: 1px solid #ddd; max-width: 300px; word-wrap: break-word;">${escapeHtml(doc.content.substring(0, 150))}${doc.content.length > 150 ? '...' : ''}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">${bm25Score}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">${temp1Percent}%</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: bold;">${userTempPercent}%</td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
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

    const rows = data.documents.map(doc => `
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(doc.id)}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(doc.title)}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(doc.content.substring(0, 150))}${doc.content.length > 150 ? '...' : ''}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">${formatRank(doc.bm25_rank)}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">${formatRank(doc.colbert_rank)}</td>
            <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: bold;">${doc.rrf_score.toFixed(6)}</td>
        </tr>
    `).join('');

    resultsDiv.innerHTML = `
        <div class="muted" style="margin-bottom: 12px;">
            Found ${data.documents.length} documents using BM25 + ColBERT reciprocal rank fusion.
        </div>
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse; margin-top: 12px;">
                <thead>
                    <tr style="background: #f5f5f5;">
                        <th style="padding: 8px; border: 1px solid #ddd;">Tool ID</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">Title</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">Content</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">BM25 Rank</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">ColBERT Rank</th>
                        <th style="padding: 8px; border: 1px solid #ddd;">RRF Score</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
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
    const listDiv = document.getElementById('documents-list');
    const tbody = document.getElementById('documents-tbody');
    const noDocsMsg = document.getElementById('no-documents-message');
    const table = document.getElementById('documents-table-element');
    
    // Count by type and provider
    const localDocs = documents.filter(doc => doc.type === 'local');
    const mcpDocs = documents.filter(doc => doc.type === 'mcp');
    
    // Count by provider
    const providers = {};
    documents.forEach(doc => {
        const provider = doc.provider || 'unknown';
        providers[provider] = (providers[provider] || 0) + 1;
    });
    
    // Update summary
    const providerSummary = Object.entries(providers)
        .map(([provider, count]) => `${provider}: ${count}`)
        .join(', ');
    
    listDiv.innerHTML = `
        <div class="muted">
            <p>Total indexed documents: ${documents.length} [Local: ${localDocs.length}, MCP: ${mcpDocs.length}]</p>
            <p style="font-size: 0.9em;">Providers: ${providerSummary}</p>
            <p style="font-size: 0.9em;">Source: ${documents.source || 'N/A'}</p>
        </div>
    `;
    
    // Update table
    if (documents.length === 0) {
        table.style.display = 'none';
        noDocsMsg.style.display = 'block';
        tbody.innerHTML = '';
    } else {
        table.style.display = 'table';
        noDocsMsg.style.display = 'none';
        
        // Sort documents: local first, then MCP
        const sortedDocuments = [...documents].sort((a, b) => {
            if (a.type === 'local' && b.type === 'mcp') return -1;
            if (a.type === 'mcp' && b.type === 'local') return 1;
            return 0;
        });

        tbody.innerHTML = sortedDocuments.map(doc => {
            const isMCP = doc.type === 'mcp';
            const isLocal = doc.type === 'local';
            
            // Style based on type
            const rowStyle = isMCP ? 'background: #e8f4ff;' : 'background: #f9f9f9;';
            const typeBadge = isMCP ? 
                '<span style="background: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">MCP</span>' :
                '<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">Local</span>';
            
            const providerBadge = doc.provider ? 
                `<span style="background: #6c757d; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">${escapeHtml(doc.provider)}</span>` :
                '<span style="color: #999;">-</span>';
            
            const deleteButton = '<span style="color: #999; font-size: 12px;" title="Documents from cache cannot be deleted via UI">-</span>';
            
            return `
                <tr style="${rowStyle}">
                    <td style="padding: 8px; border: 1px solid #ddd; max-width: 150px; word-wrap: break-word;">${escapeHtml(doc.id)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; max-width: 200px; word-wrap: break-word;">${escapeHtml(doc.title)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; max-width: 300px; word-wrap: break-word;">${escapeHtml(doc.description ? doc.description.substring(0, 100) : '')}${doc.description && doc.description.length > 100 ? '...' : ''}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${providerBadge}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${typeBadge}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(doc.category || '-')}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center; width: 80px;">${deleteButton}</td>
                </tr>
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
        status.textContent = `Available using ${capability.model} with FastEmbed ONNX late interaction.`;
    }
    updateHybridSearchControls();
}

function updateSearchTabDefaults(settings) {
    document.getElementById('search-temperature').value = settings.bm25s.temperature;
    document.getElementById('search-ignore-zero').checked = settings.bm25s.ignore_zero;
    document.getElementById('search-cutoff').value = settings.bm25s.llm_tools_cutoff;
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
    const tbody = document.getElementById('providers-tbody');
    const noProvidersMsg = document.getElementById('no-providers-message');
    const table = document.getElementById('providers-table-element');
    
    if (providers.length === 0) {
        table.style.display = 'none';
        noProvidersMsg.style.display = 'block';
        tbody.innerHTML = '';
    } else {
        table.style.display = 'table';
        noProvidersMsg.style.display = 'none';
        
        tbody.innerHTML = providers.map(provider => {
            const enabledBadge = provider.enabled ? 
                '<span style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">Enabled</span>' :
                '<span style="background: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">Disabled</span>';
            const discoverButton = provider.enabled
                ? `<button onclick="discoverProviderTools('${escapeHtml(provider.id)}')" style="background: #007bff; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; margin-right: 4px;" title="Discover tools">🔍</button>`
                : '<button disabled style="background: #adb5bd; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: not-allowed; margin-right: 4px;" title="Provider is disabled">🔍</button>';
            const removeButton = provider.enabled
                ? `<button onclick="disableProvider('${escapeHtml(provider.id)}')" style="background: #dc3545; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer;" title="Remove provider">×</button>`
                : '';
            
            const endpoint = provider.transport === 'stdio' ? 
                `${provider.command} ${provider.args.join(' ')}` : 
                (provider.endpoint || '-');
            
            return `
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd; max-width: 150px; word-wrap: break-word;">${escapeHtml(provider.id)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; max-width: 200px; word-wrap: break-word;">${escapeHtml(provider.name)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(provider.transport)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; max-width: 250px; word-wrap: break-word;">${escapeHtml(endpoint)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${escapeHtml(provider.auth?.type || 'none')}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${enabledBadge}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center; width: 140px;">
                        <button onclick="editProvider('${escapeHtml(provider.id)}')" style="background: #6c757d; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; margin-right: 4px;" title="Edit provider">✎</button>
                        ${discoverButton}
                        ${removeButton}
                    </td>
                </tr>
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
        const toolsTbody = document.getElementById('discovered-tools-tbody');

        progressBox.style.display = 'block';
        toolsBox.style.display = 'none';
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

        // Show discovered tools in table
        toolsBox.style.display = 'block';
        toolsTbody.innerHTML = '';

        if (data.tools && data.tools.length > 0) {
            data.tools.forEach(tool => {
                const row = document.createElement('tr');
                const paramsStr = tool.params ? JSON.stringify(tool.params) : '{}';
                row.innerHTML = `
                    <td style="padding: 6px; border: 1px solid #ddd;">${escapeHtml(tool.title || tool.tool_name || '')}</td>
                    <td style="padding: 6px; border: 1px solid #ddd; max-width: 300px; word-wrap: break-word;">${escapeHtml(tool.description || '').substring(0, 100)}${tool.description && tool.description.length > 100 ? '...' : ''}</td>
                    <td style="padding: 6px; border: 1px solid #ddd; max-width: 200px; word-wrap: break-word; font-family: monospace; font-size: 11px;">${escapeHtml(paramsStr).substring(0, 150)}${paramsStr.length > 150 ? '...' : ''}</td>
                    <td style="padding: 6px; border: 1px solid #ddd;">${escapeHtml(tool.category || 'general')}</td>
                `;
                toolsTbody.appendChild(row);
            });
        } else {
            const row = document.createElement('tr');
            row.innerHTML = `<td colspan="4" style="padding: 6px; border: 1px solid #ddd; text-align: center;">No tools discovered</td>`;
            toolsTbody.appendChild(row);
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
