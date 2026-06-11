/**
 * BM25S Retriever UI JavaScript
 */

// Global state
let currentDocuments = [];
let currentSettings = {};

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
    
    try {
        showMessage('search-results', 'Searching...', 'info');
        
        // Make two API calls - one with temp 1.0 and one with user temp
        const [response1, response2] = await Promise.all([
            fetch('/retrieve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    temperature: 1.0,
                    llm_tools_cutoff: cutoff,
                    ignore_zero: ignoreZero
                })
            }),
            fetch('/retrieve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    temperature,
                    llm_tools_cutoff: cutoff,
                    ignore_zero: ignoreZero
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
                        <th style="padding: 8px; text-align: left; border: 1px solid #ddd;">Document ID</th>
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

function clearSearch() {
    document.getElementById('search-query').value = '';
    document.getElementById('search-results').innerHTML = '<div class="muted">Enter a query to search documents.</div>';
}

// Documents tab functionality
function initDocumentsTab() {
    const addBtn = document.getElementById('add-document-btn');
    const reloadBtn = document.getElementById('reload-index-btn');
    const saveBtn = document.getElementById('save-document-btn');
    const fileSelector = document.getElementById('file-selector');
    const switchFileBtn = document.getElementById('switch-file-btn');
    
    addBtn?.addEventListener('click', () => {
        document.getElementById('add-document-modal').style.display = 'block';
    });
    
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
    
    // Count user-added vs YAML documents
    const userDocs = documents.filter(doc => doc.metadata && doc.metadata.source === 'ui');
    const yamlDocs = documents.filter(doc => doc.metadata && doc.metadata.source === 'yaml');
    
    // Update summary
    listDiv.innerHTML = `
        <div class="muted">
            <p>Total indexed documents: ${documents.length} [YAML File: ${yamlDocs.length}, User Added: ${userDocs.length}]</p>
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
        
        // Sort documents: user-added first, then YAML
    const sortedDocuments = [...documents].sort((a, b) => {
        const aIsUser = a.metadata && a.metadata.source === 'ui';
        const bIsUser = b.metadata && b.metadata.source === 'ui';
        if (aIsUser && !bIsUser) return -1;
        if (!aIsUser && bIsUser) return 1;
        return 0;
    });

    tbody.innerHTML = sortedDocuments.map(doc => {
            const isFromUI = doc.metadata && doc.metadata.source === 'ui';
            const isFromYaml = doc.metadata && doc.metadata.source === 'yaml';
            const deleteButton = isFromUI ? 
                `<button onclick="deleteDocument('${escapeHtml(doc.id)}')" style="background: #ff4444; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer;" title="Delete user-added document">
                    <span style="font-size: 12px;">×</span>
                </button>` :
                '<span style="color: #999; font-size: 12px;" title="This document cannot be deleted via UI">-</span>';
            
            let sourceLabel = '';
            if (isFromYaml) {
                sourceLabel = ' <small style="color: #666;">(YAML)</small>';
            } else if (isFromUI) {
                sourceLabel = ' <small style="color: #007bff;">(UI)</small>';
            }
            
            return `
                <tr style="${isFromYaml ? 'background: #f9f9f9;' : ''}">
                    <td style="padding: 8px; border: 1px solid #ddd; max-width: 150px; word-wrap: break-word;">${escapeHtml(doc.id)}${sourceLabel}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; max-width: 200px; word-wrap: break-word;">${escapeHtml(doc.title)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; max-width: 300px; word-wrap: break-word;">${escapeHtml(doc.content.substring(0, 100))}${doc.content.length > 100 ? '...' : ''}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; max-width: 150px; word-wrap: break-word;">${doc.keywords && doc.keywords.length > 0 ? doc.keywords.map(kw => escapeHtml(kw)).join(', ') : '-'}</td>
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
    
    // Also update search tab defaults
    updateSearchTabDefaults(settings);
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

async function loadInitialData() {
    await Promise.all([
        loadSettings(),
        loadDocuments(),
        loadStatus(),
        loadDocumentFiles()
    ]);
}
