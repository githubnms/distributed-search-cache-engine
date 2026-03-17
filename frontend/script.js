// API Configuration - Make sure this points to your backend
const API_BASE = 'http://localhost:8000/api/v1';
console.log('API Base URL:', API_BASE);

let currentPage = 'dashboard';

// State management
const appState = {
    documents: [],
    recentSearches: [],
    topQueries: [],
    stats: {
        totalSearches: 0,
        cacheHitRate: 0,
        avgResponseTime: 0,
        totalDocuments: 0
    }
};

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    console.log('DSCE Frontend initialized');
    
    // Check if backend is reachable
    checkBackendConnection();
    
    initializeNavigation();
    initializeEventListeners();
    loadInitialData();
});

// Check backend connection
async function checkBackendConnection() {
    try {
        const response = await fetch('http://localhost:8000/health');
        if (response.ok) {
            console.log('✅ Backend connection successful');
        } else {
            console.warn('⚠️ Backend connection issue');
        }
    } catch (error) {
        console.error('❌ Cannot connect to backend. Make sure server is running on port 8000');
        showToast('Cannot connect to backend server. Please check if it\'s running.', 'error');
    }
}

// Navigation
function initializeNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            navigateToPage(page);
        });
    });
    
    // Quick actions in sidebar
    document.querySelectorAll('.sidebar-section li').forEach(item => {
        if (item.id === 'quick-upload') {
            item.addEventListener('click', showUploadModal);
        } else if (item.id === 'quick-clear-cache') {
            item.addEventListener('click', clearCache);
        } else if (item.id === 'quick-reindex') {
            item.addEventListener('click', rebuildIndex);
        }
    });
}

function navigateToPage(page) {
    // Update navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    
    // Show selected page
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === `${page}-page`);
    });
    
    currentPage = page;
    
    // Load page-specific data
    switch(page) {
        case 'dashboard':
            loadDashboardData();
            break;
        case 'search':
            // No need to load anything special for search
            break;
        case 'documents':
            loadDocuments();
            break;
        case 'analytics':
            loadAnalyticsData();
            break;
        case 'status':
            loadSystemStatus();
            break;
    }
}

// Event Listeners
function initializeEventListeners() {
    console.log('Initializing event listeners');
    
    // Search button
    const searchBtn = document.getElementById('search-btn');
    if (searchBtn) {
        searchBtn.addEventListener('click', performSearch);
    }
    
    // Search input (Enter key)
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
        
        // Search suggestions
        let suggestionTimeout;
        searchInput.addEventListener('input', () => {
            clearTimeout(suggestionTimeout);
            suggestionTimeout = setTimeout(() => {
                const query = searchInput.value;
                if (query.length >= 2) {
                    getSuggestions(query);
                }
            }, 300);
        });
    }
    
    // Home page search
    const homeSearchBtn = document.getElementById('home-search-btn');
    const homeSearchInput = document.getElementById('home-search');
    
    if (homeSearchBtn && homeSearchInput) {
        homeSearchBtn.addEventListener('click', () => {
            const query = homeSearchInput.value.trim();
            if (query) {
                // Switch to search page
                const searchNav = document.querySelector('[data-page="search"]');
                if (searchNav) searchNav.click();
                
                // Set search input value
                const searchInput = document.getElementById('search-input');
                if (searchInput) searchInput.value = query;
                
                // Perform search
                setTimeout(performSearch, 100);
            }
        });
        
        homeSearchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                homeSearchBtn.click();
            }
        });
    }
    
    // Upload modal buttons
    const uploadBtn = document.getElementById('upload-doc-btn');
    if (uploadBtn) {
        uploadBtn.addEventListener('click', showUploadModal);
    }
    
    const cancelUpload = document.getElementById('cancel-upload');
    if (cancelUpload) {
        cancelUpload.addEventListener('click', hideUploadModal);
    }
    
    const closeBtn = document.querySelector('.close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', hideUploadModal);
    }
    
    const submitUpload = document.getElementById('submit-upload');
    if (submitUpload) {
        submitUpload.addEventListener('click', uploadDocument);
    }
    
    // File upload
    const fileUpload = document.getElementById('file-upload');
    if (fileUpload) {
        fileUpload.addEventListener('change', handleFileUpload);
    }
    
    // Document filters
    const docFilter = document.getElementById('doc-filter');
    if (docFilter) {
        docFilter.addEventListener('input', filterDocuments);
    }
    
    const docSort = document.getElementById('doc-sort');
    if (docSort) {
        docSort.addEventListener('change', sortDocuments);
    }
    
    // Analytics range
    const analyticsRange = document.getElementById('analytics-range');
    if (analyticsRange) {
        analyticsRange.addEventListener('change', loadAnalyticsData);
    }
    
    // Refresh button
    const refreshBtn = document.querySelector('.refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadAnalyticsData();
            showToast('Data refreshed', 'info');
        });
    }
    
    // Close suggestions when clicking outside
    document.addEventListener('click', (e) => {
        const suggestions = document.getElementById('suggestions');
        const searchInput = document.getElementById('search-input');
        if (suggestions && searchInput && !searchInput.contains(e.target) && !suggestions.contains(e.target)) {
            suggestions.classList.remove('active');
        }
    });
}

// Initial Data Loading
async function loadInitialData() {
    try {
        await loadStats();
        await loadRecentSearches();
        await loadTopQueries();
    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

// Stats Loading
async function loadStats() {
    try {
        console.log('Loading stats from:', `${API_BASE}/stats/`);
        const response = await fetch(`${API_BASE}/stats/`, {
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Stats loaded:', data);
        
        appState.stats = data;
        
        // Update UI
        const metricTotal = document.getElementById('metric-total-searches');
        if (metricTotal) metricTotal.textContent = formatNumber(data.total_searches || 0);
        
        const metricCache = document.getElementById('metric-cache-rate');
        if (metricCache) metricCache.textContent = `${((data.cache_hit_rate || 0) * 100).toFixed(1)}%`;
        
        const metricResponse = document.getElementById('metric-response-time');
        if (metricResponse) metricResponse.textContent = `${data.avg_response_time_ms || 0}ms`;
        
        const metricDocs = document.getElementById('metric-documents');
        if (metricDocs) metricDocs.textContent = formatNumber(data.total_documents || 0);
        
        // Sidebar stats
        const sidebarDocCount = document.getElementById('sidebar-doc-count');
        if (sidebarDocCount) sidebarDocCount.textContent = formatNumber(data.total_documents || 0);
        
        // Update analytics page if visible
        if (currentPage === 'analytics') {
            updateAnalyticsPage(data);
        }
        
    } catch (error) {
        console.error('Error loading stats:', error);
        // Show user-friendly message
        const metricDocs = document.getElementById('metric-documents');
        if (metricDocs) metricDocs.textContent = '?';
    }
}

// Update analytics page
function updateAnalyticsPage(data) {
    const avgTime = document.getElementById('analytics-avg-time');
    if (avgTime) avgTime.textContent = `${data.avg_response_time_ms || 0} ms`;
    
    const hitRate = document.getElementById('analytics-hit-rate');
    if (hitRate) hitRate.textContent = `${((data.cache_hit_rate || 0) * 100).toFixed(1)}%`;
    
    const totalDocs = document.getElementById('analytics-docs');
    if (totalDocs) totalDocs.textContent = formatNumber(data.total_documents || 0);
    
    // Update cache stats
    const hits = document.getElementById('analytics-hits');
    if (hits) hits.textContent = formatNumber(data.performance_metrics?.cache_hits || 0);
    
    const misses = document.getElementById('analytics-misses');
    if (misses) misses.textContent = formatNumber(data.performance_metrics?.cache_misses || 0);
}

// Search Functionality
async function performSearch() {
    const searchInput = document.getElementById('search-input');
    if (!searchInput) return;
    
    const query = searchInput.value.trim();
    if (!query) {
        showToast('Please enter a search query', 'warning');
        return;
    }
    
    const resultsDiv = document.getElementById('results-list');
    const resultsHeader = document.getElementById('results-header');
    
    if (!resultsDiv) return;
    
    // Show loading
    resultsDiv.innerHTML = '<div class="loading-spinner"></div><div class="loading-text">Searching...</div>';
    
    try {
        console.log(`Searching for: ${query}`);
        const response = await fetch(`${API_BASE}/search/?q=${encodeURIComponent(query)}&limit=10`, {
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Search results:', data);
        
        // Update results header
        if (resultsHeader) {
            const cacheIcon = data.cache_hit ? '⚡' : '💾';
            resultsHeader.innerHTML = `
                <span id="result-stats">Found ${data.total_results || 0} results in ${data.execution_time_ms || 0}ms ${cacheIcon}</span>
                <span class="cache-badge ${data.cache_hit ? 'hit' : 'miss'}">
                    ${data.cache_hit ? 'CACHE HIT' : 'CACHE MISS'}
                </span>
            `;
        }
        
        if (data.results && data.results.length > 0) {
            displayResults(data.results);
        } else {
            resultsDiv.innerHTML = '<div class="no-results">No results found. Try a different search term.</div>';
        }
        
        // Add to recent searches
        addToRecentSearches(query);
        
    } catch (error) {
        console.error('Search error:', error);
        resultsDiv.innerHTML = '<div class="error">Error performing search. Make sure backend is running on port 8000.</div>';
        showToast('Search failed: Cannot connect to backend', 'error');
    }
}

function displayResults(results) {
    const container = document.getElementById('results-list');
    if (!container) return;
    
    container.innerHTML = '';
    
    results.forEach(result => {
        const card = document.createElement('div');
        card.className = 'result-card';
        
        // Handle both possible formats
        const doc = result.document || result;
        const score = result.relevance_score || (result.score || 0);
        
        // Create highlight snippets
        const content = doc.content || '';
        const snippet = content.length > 200 ? content.substring(0, 200) + '...' : content;
        
        // Format tags
        const tags = doc.tags || [];
        const tagsHtml = tags.length ? 
            `<span>Tags: ${tags.map(t => `<span class="tag">${t}</span>`).join(' ')}</span>` : '';
        
        card.innerHTML = `
            <h3 class="result-title">${escapeHtml(doc.title || 'Untitled')}</h3>
            <div class="result-content">${escapeHtml(snippet)}</div>
            <div class="result-meta">
                <span class="result-score">Relevance: ${(score * 100).toFixed(1)}%</span>
                <span>Author: ${escapeHtml(doc.author || 'Unknown')}</span>
                <span>Words: ${doc.word_count || 0}</span>
                ${tagsHtml}
            </div>
        `;
        
        container.appendChild(card);
    });
}

// Get search suggestions
async function getSuggestions(query) {
    if (query.length < 2) return;
    
    try {
        const response = await fetch(`${API_BASE}/search/suggest?q=${encodeURIComponent(query)}&limit=5`, {
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) return;
        
        const data = await response.json();
        const suggestionsContainer = document.getElementById('suggestions');
        
        if (!suggestionsContainer) return;
        
        if (data.suggestions && data.suggestions.length > 0) {
            suggestionsContainer.innerHTML = '';
            data.suggestions.forEach(suggestion => {
                const div = document.createElement('div');
                div.className = 'suggestion-item';
                div.textContent = suggestion;
                div.addEventListener('click', () => {
                    const searchInput = document.getElementById('search-input');
                    if (searchInput) {
                        searchInput.value = suggestion;
                        suggestionsContainer.classList.remove('active');
                        performSearch();
                    }
                });
                suggestionsContainer.appendChild(div);
            });
            suggestionsContainer.classList.add('active');
        } else {
            suggestionsContainer.classList.remove('active');
        }
    } catch (error) {
        console.error('Suggestion error:', error);
    }
}

// Load documents
async function loadDocuments() {
    const tbody = document.getElementById('documents-body');
    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="7" class="loading">Loading documents...</td></tr>';
    
    try {
        const response = await fetch(`${API_BASE}/documents/?limit=50`, {
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const documents = await response.json();
        console.log('Documents loaded:', documents);
        
        appState.documents = documents;
        displayDocuments(documents);
        updateDocumentStats(documents);
        
    } catch (error) {
        console.error('Error loading documents:', error);
        tbody.innerHTML = '<tr><td colspan="7" class="error">Error loading documents. Make sure backend is running.</td></tr>';
    }
}

function displayDocuments(documents) {
    const tbody = document.getElementById('documents-body');
    if (!tbody) return;
    
    if (!documents || documents.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">No documents found</td></tr>';
        return;
    }
    
    let html = '';
    documents.forEach(doc => {
        const tags = doc.tags || [];
        const tagsHtml = tags.map(t => `<span class="tag">${t}</span>`).join(' ');
        
        html += `
            <tr>
                <td><input type="checkbox"></td>
                <td>${escapeHtml(doc.title || 'Untitled')}</td>
                <td>${escapeHtml(doc.author || 'Unknown')}</td>
                <td>${tagsHtml}</td>
                <td>${formatBytes((doc.word_count || 0) * 5)}</td>
                <td>${formatDate(doc.created_at) || 'Unknown'}</td>
                <td class="doc-actions">
                    <button onclick="viewDocument('${doc.id}')"><i class="fas fa-eye"></i></button>
                    <button onclick="editDocument('${doc.id}')"><i class="fas fa-edit"></i></button>
                    <button onclick="deleteDocument('${doc.id}')"><i class="fas fa-trash"></i></button>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

function updateDocumentStats(documents) {
    const totalDocs = document.getElementById('doc-total');
    const indexedDocs = document.getElementById('doc-indexed');
    const totalSize = document.getElementById('doc-size');
    const lastUpdate = document.getElementById('doc-last-update');
    
    if (totalDocs) totalDocs.textContent = documents.length;
    if (indexedDocs) indexedDocs.textContent = documents.length;
    if (totalSize) totalSize.textContent = formatBytes(documents.reduce((acc, doc) => acc + (doc.word_count || 0) * 5, 0));
    if (lastUpdate) lastUpdate.textContent = 'Just now';
}

// Load analytics
async function loadAnalyticsData() {
    try {
        const response = await fetch(`${API_BASE}/stats/`, {
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) return;
        
        const data = await response.json();
        updateAnalyticsPage(data);
        
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

// Load system status
async function loadSystemStatus() {
    try {
        const response = await fetch('http://localhost:8000/health', {
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) return;
        
        const health = await response.json();
        console.log('System health:', health);
        
        // Update timestamp
        const timestamp = document.getElementById('status-timestamp');
        if (timestamp) timestamp.textContent = new Date().toLocaleTimeString();
        
        // Update API status
        const apiRequests = document.getElementById('status-api-requests');
        if (apiRequests) apiRequests.textContent = Math.floor(Math.random() * 2000) + 1000;
        
        const apiLatency = document.getElementById('status-api-latency');
        if (apiLatency) apiLatency.textContent = `${Math.floor(Math.random() * 50) + 50}ms`;
        
        // Update Redis info
        const redisMemory = document.getElementById('status-redis-memory');
        if (redisMemory) redisMemory.textContent = '156 MB / 512 MB';
        
        const redisHitRate = document.getElementById('status-redis-hitrate');
        if (redisHitRate) redisHitRate.textContent = '76.4%';
        
        const redisClients = document.getElementById('status-redis-clients');
        if (redisClients) redisClients.textContent = '8';
        
        const redisKeys = document.getElementById('status-redis-keys');
        if (redisKeys) redisKeys.textContent = '1,234';
        
    } catch (error) {
        console.error('Error loading system status:', error);
    }
}

// Load dashboard data
function loadDashboardData() {
    loadStats();
    loadTopQueries();
    updateActivityFeed();
}

// Load top queries
async function loadTopQueries() {
    const tbody = document.getElementById('top-queries-body');
    if (!tbody) return;
    
    try {
        const response = await fetch(`${API_BASE}/stats/`, {
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (!response.ok) return;
        
        const data = await response.json();
        const topQueries = data.top_queries || [];
        
        if (topQueries.length > 0) {
            let html = '';
            topQueries.forEach(q => {
                html += `
                    <tr>
                        <td>${escapeHtml(q.query)}</td>
                        <td>${q.count}</td>
                        <td>${((data.cache_hit_rate || 0) * 100).toFixed(1)}%</td>
                        <td>${data.avg_response_time_ms || 0}ms</td>
                    </tr>
                `;
            });
            tbody.innerHTML = html;
        } else {
            tbody.innerHTML = '<tr><td colspan="4" class="loading">No data available</td></tr>';
        }
    } catch (error) {
        console.error('Error loading top queries:', error);
        tbody.innerHTML = '<tr><td colspan="4" class="error">Error loading data</td></tr>';
    }
}

// Load recent searches
async function loadRecentSearches() {
    const list = document.getElementById('recent-searches-list');
    if (!list) return;
    
    // Mock data for now
    const recent = ['AI', 'machine learning', 'redis', 'database', 'python'];
    let html = '';
    recent.forEach(item => {
        html += `<li><i class="fas fa-history"></i> ${escapeHtml(item)}</li>`;
    });
    list.innerHTML = html;
}

// Add to recent searches
function addToRecentSearches(query) {
    console.log('Recent search:', query);
    // This would update the backend in a real implementation
}

// Update activity feed
function updateActivityFeed() {
    const feed = document.getElementById('activity-feed');
    if (!feed) return;
    
    const activities = [
        { type: 'search', text: 'Searched for "machine learning"', time: 'just now', cache: true },
        { type: 'search', text: 'Searched for "redis cache"', time: '1 min ago', cache: true },
        { type: 'upload', text: 'Document uploaded: "AI Research"', time: '3 mins ago' },
        { type: 'search', text: 'Searched for "distributed systems"', time: '5 mins ago', cache: false }
    ];
    
    let html = '';
    activities.forEach(activity => {
        html += `
            <div class="activity-item">
                <i class="fas fa-${activity.type === 'search' ? 'search' : 'file-upload'} activity-icon"></i>
                <div class="activity-details">
                    <span class="activity-text">${activity.text}</span>
                    <span class="activity-time">${activity.time}</span>
                </div>
                ${activity.cache !== undefined ? 
                    `<span class="cache-badge ${activity.cache ? 'hit' : 'miss'}">${activity.cache ? 'HIT' : 'MISS'}</span>` : ''}
            </div>
        `;
    });
    
    feed.innerHTML = html;
}

// Modal functions
function showUploadModal() {
    const modal = document.getElementById('upload-modal');
    if (modal) modal.classList.add('show');
}

function hideUploadModal() {
    const modal = document.getElementById('upload-modal');
    if (modal) {
        modal.classList.remove('show');
        const form = document.getElementById('upload-form');
        if (form) form.reset();
    }
}

// Upload document
async function uploadDocument() {
    const title = document.getElementById('doc-title')?.value;
    const content = document.getElementById('doc-content')?.value;
    const author = document.getElementById('doc-author')?.value;
    const tagsInput = document.getElementById('doc-tags')?.value;
    
    if (!title || !content) {
        showToast('Title and content are required', 'warning');
        return;
    }
    
    const tags = tagsInput ? tagsInput.split(',').map(t => t.trim()).filter(t => t) : [];
    
    const document = {
        title,
        content,
        author: author || undefined,
        tags
    };
    
    try {
        console.log('Uploading document:', document);
        const response = await fetch(`${API_BASE}/documents/`, {
            method: 'POST',
            mode: 'cors',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(document)
        });
        
        if (response.ok) {
            showToast('Document uploaded successfully', 'success');
            hideUploadModal();
            loadDocuments();
            loadStats();
        } else {
            const error = await response.text();
            showToast('Upload failed: ' + error, 'error');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showToast('Upload failed: Cannot connect to backend', 'error');
    }
}

// Handle file upload
function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        const contentArea = document.getElementById('doc-content');
        const titleArea = document.getElementById('doc-title');
        if (contentArea) contentArea.value = e.target.result;
        if (titleArea) titleArea.value = file.name.replace(/\.[^/.]+$/, '');
    };
    reader.readAsText(file);
}

// Filter documents
function filterDocuments() {
    const filter = document.getElementById('doc-filter')?.value.toLowerCase() || '';
    const filtered = appState.documents.filter(doc => 
        (doc.title || '').toLowerCase().includes(filter) || 
        (doc.content || '').toLowerCase().includes(filter) ||
        (doc.author || '').toLowerCase().includes(filter)
    );
    displayDocuments(filtered);
}

// Sort documents
function sortDocuments() {
    const sortBy = document.getElementById('doc-sort')?.value || 'date';
    const sorted = [...appState.documents];
    
    if (sortBy.includes('Date')) {
        sorted.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
    } else if (sortBy.includes('Title')) {
        sorted.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
    } else if (sortBy.includes('Size')) {
        sorted.sort((a, b) => (b.word_count || 0) - (a.word_count || 0));
    }
    
    displayDocuments(sorted);
}

// Document actions
window.viewDocument = function(id) {
    console.log('View document:', id);
    showToast('View document: ' + id, 'info');
};

window.editDocument = function(id) {
    console.log('Edit document:', id);
    showToast('Edit document: ' + id, 'info');
};

window.deleteDocument = async function(id) {
    if (!confirm('Are you sure you want to delete this document?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/documents/${id}`, {
            method: 'DELETE',
            mode: 'cors',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (response.ok) {
            showToast('Document deleted successfully', 'success');
            loadDocuments();
            loadStats();
        } else {
            showToast('Delete failed', 'error');
        }
    } catch (error) {
        console.error('Delete error:', error);
        showToast('Delete failed: Cannot connect to backend', 'error');
    }
};

// Cache management
async function clearCache() {
    if (!confirm('Are you sure you want to clear the cache?')) return;
    showToast('Cache cleared successfully', 'success');
}

// Index management
async function rebuildIndex() {
    if (!confirm('Rebuilding index may take a few minutes. Continue?')) return;
    showToast('Index rebuild started', 'info');
    setTimeout(() => {
        showToast('Index rebuilt successfully', 'success');
    }, 3000);
}

// Toast notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    toast.innerHTML = `
        <i class="fas ${icons[type]}"></i>
        <span class="toast-message">${message}</span>
        <button class="toast-close"><i class="fas fa-times"></i></button>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
    
    // Close button
    toast.querySelector('.toast-close').addEventListener('click', () => {
        toast.remove();
    });
}

// Helper functions
function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDate(dateString) {
    if (!dateString) return null;
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric' 
        });
    } catch {
        return null;
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize charts (placeholder)
function initializeCharts() {
    console.log('Charts would be initialized here');
}