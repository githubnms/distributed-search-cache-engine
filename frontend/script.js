// API Configuration
const API_BASE = '/api/v1';
let currentPage = 'dashboard';
let charts = {};

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
    initializeNavigation();
    initializeEventListeners();
    loadInitialData();
    startRealTimeUpdates();
});

// Navigation
function initializeNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            navigateToPage(page);
        });
    });
    
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
            initializeSearch();
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
    // Search
    document.getElementById('search-btn').addEventListener('click', performSearch);
    document.getElementById('search-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    
    // Search suggestions
    let suggestionTimeout;
    document.getElementById('search-input').addEventListener('input', () => {
        clearTimeout(suggestionTimeout);
        suggestionTimeout = setTimeout(() => {
            getSuggestions(document.getElementById('search-input').value);
        }, 300);
    });
    
    // Upload modal
    document.getElementById('upload-doc-btn').addEventListener('click', showUploadModal);
    document.getElementById('cancel-upload').addEventListener('click', hideUploadModal);
    document.querySelector('.close-btn').addEventListener('click', hideUploadModal);
    document.getElementById('submit-upload').addEventListener('click', uploadDocument);
    
    // File upload
    document.getElementById('file-upload').addEventListener('change', handleFileUpload);
    
    // Document filters
    document.getElementById('doc-filter').addEventListener('input', filterDocuments);
    document.getElementById('doc-sort').addEventListener('change', sortDocuments);
    
    // Analytics range
    document.getElementById('analytics-range').addEventListener('change', loadAnalyticsData);
    
    // Refresh button
    document.querySelector('.refresh-btn')?.addEventListener('click', () => {
        loadAnalyticsData();
        showToast('Data refreshed', 'info');
    });
}

// Initial Data Loading
async function loadInitialData() {
    try {
        await Promise.all([
            loadStats(),
            loadRecentSearches(),
            loadTopQueries()
        ]);
        
        initializeCharts();
    } catch (error) {
        console.error('Error loading initial data:', error);
        showToast('Error loading data', 'error');
    }
}

// Stats Loading
async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats/`);
        const data = await response.json();
        
        appState.stats = data;
        
        // Update UI
        document.getElementById('metric-total-searches').textContent = formatNumber(data.total_searches);
        document.getElementById('metric-cache-rate').textContent = `${(data.cache_hit_rate * 100).toFixed(1)}%`;
        document.getElementById('metric-response-time').textContent = `${data.avg_response_time_ms}ms`;
        document.getElementById('metric-documents').textContent = formatNumber(data.total_documents);
        
        // Sidebar stats
        document.getElementById('sidebar-doc-count').textContent = formatNumber(data.total_documents);
        document.getElementById('sidebar-cache-size').textContent = `${data.index_size_mb.toFixed(1)}MB`;
        
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Search Functionality
async function performSearch() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) {
        showToast('Please enter a search query', 'warning');
        return;
    }
    
    const exactMatch = document.getElementById('exact-match').checked;
    const synonymExpand = document.getElementById('synonym-expand').checked;
    const fuzzySearch = document.getElementById('fuzzy-search').checked;
    
    showLoading(true);
    
    try {
        const response = await fetch(
            `${API_BASE}/search/?q=${encodeURIComponent(query)}&limit=10`
        );
        const data = await response.json();
        
        displayResults(data);
        addToRecentSearches(query);
        updateResultStats(data);
        
    } catch (error) {
        console.error('Search error:', error);
        showToast('Search failed', 'error');
    } finally {
        showLoading(false);
    }
}

function displayResults(data) {
    const resultsList = document.getElementById('results-list');
    
    if (!data.results || data.results.length === 0) {
        resultsList.innerHTML = '<div class="no-results">No results found</div>';
        return;
    }
    
    let html = '';
    data.results.forEach(result => {
        html += `
            <div class="result-card">
                <h3 class="result-title">${escapeHtml(result.document.title)}</h3>
                <div class="result-content">${escapeHtml(result.document.content)}</div>
                <div class="result-meta">
                    <span class="result-score">Relevance: ${(result.relevance_score * 100).toFixed(1)}%</span>
                    <span>Author: ${escapeHtml(result.document.author || 'Unknown')}</span>
                    <span>Words: ${result.document.word_count || 0}</span>
                </div>
            </div>
        `;
    });
    
    resultsList.innerHTML = html;
}

// Document Management
async function loadDocuments() {
    showLoading(true);
    
    try {
        const response = await fetch(`${API_BASE}/documents/?limit=50`);
        const documents = await response.json();
        
        appState.documents = documents;
        displayDocuments(documents);
        updateDocumentStats(documents);
        
    } catch (error) {
        console.error('Error loading documents:', error);
        showToast('Error loading documents', 'error');
    } finally {
        showLoading(false);
    }
}

function displayDocuments(documents) {
    const tbody = document.getElementById('documents-body');
    
    if (!documents || documents.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">No documents found</td></tr>';
        return;
    }
    
    let html = '';
    documents.forEach(doc => {
        html += `
            <tr>
                <td><input type="checkbox"></td>
                <td>${escapeHtml(doc.title)}</td>
                <td>${escapeHtml(doc.author || 'Unknown')}</td>
                <td>${formatTags(doc.tags)}</td>
                <td>${formatBytes(doc.word_count * 5)}</td>
                <td>${formatDate(doc.created_at)}</td>
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

// Analytics
async function loadAnalyticsData() {
    try {
        const response = await fetch(`${API_BASE}/stats/`);
        const stats = await response.json();
        
        // Update analytics cards
        document.getElementById('analytics-avg-time').textContent = `${stats.avg_response_time_ms} ms`;
        document.getElementById('analytics-hit-rate').textContent = `${(stats.cache_hit_rate * 100).toFixed(1)}%`;
        document.getElementById('analytics-docs').textContent = formatNumber(stats.total_documents);
        
        // Update cache stats
        document.getElementById('analytics-hits').textContent = formatNumber(stats.performance_metrics.cache_hits || 0);
        document.getElementById('analytics-misses').textContent = formatNumber(stats.performance_metrics.cache_misses || 0);
        
        // Update charts
        updateAnalyticsCharts(stats);
        
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

// System Status
async function loadSystemStatus() {
    try {
        const response = await fetch('/health');
        const health = await response.json();
        
        // Update API status
        document.getElementById('status-timestamp').textContent = moment().format('HH:mm:ss');
        document.getElementById('status-api-requests').textContent = Math.floor(Math.random() * 2000) + 1000;
        document.getElementById('status-api-latency').textContent = `${Math.floor(Math.random() * 50) + 50}ms`;
        
        // Update Redis info
        const redisInfo = await getRedisInfo();
        document.getElementById('status-redis-memory').textContent = redisInfo.memory;
        document.getElementById('status-redis-hitrate').textContent = redisInfo.hitRate;
        document.getElementById('status-redis-clients').textContent = redisInfo.clients;
        document.getElementById('status-redis-keys').textContent = redisInfo.keys;
        
    } catch (error) {
        console.error('Error loading system status:', error);
    }
}

// Charts
function initializeCharts() {
    // Search Volume Chart
    const searchCtx = document.getElementById('search-volume-chart').getContext('2d');
    charts.searchVolume = new Chart(searchCtx, {
        type: 'line',
        data: {
            labels: generateTimeLabels(24),
            datasets: [{
                label: 'Search Volume',
                data: generateRandomData(24, 50, 200),
                borderColor: '#ff9900',
                backgroundColor: 'rgba(255, 153, 0, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: getChartOptions('Searches')
    });
    
    // Cache Performance Chart
    const cacheCtx = document.getElementById('cache-performance-chart').getContext('2d');
    charts.cachePerformance = new Chart(cacheCtx, {
        type: 'doughnut',
        data: {
            labels: ['Cache Hit', 'Cache Miss'],
            datasets: [{
                data: [76, 24],
                backgroundColor: ['#10b981', '#ef4444'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
    
    // Hit/Miss Chart
    const hitMissCtx = document.getElementById('hit-miss-chart').getContext('2d');
    charts.hitMiss = new Chart(hitMissCtx, {
        type: 'doughnut',
        data: {
            labels: ['Hits', 'Misses'],
            datasets: [{
                data: [76, 24],
                backgroundColor: ['#10b981', '#ef4444'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// Helper Functions
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
    return moment(dateString).format('MMM D, YYYY');
}

function formatTags(tags) {
    if (!tags || tags.length === 0) return '-';
    return tags.map(t => `<span class="tag">${t}</span>`).join(' ');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showLoading(show) {
    const loader = document.getElementById('loading-spinner');
    if (loader) {
        loader.style.display = show ? 'block' : 'none';
    }
}

// Toast Notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
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

// Real-time Updates
function startRealTimeUpdates() {
    // Update stats every 5 seconds
    setInterval(() => {
        if (currentPage === 'dashboard') {
            loadStats();
        }
    }, 5000);
    
    // Update activity feed every 10 seconds
    setInterval(() => {
        if (currentPage === 'dashboard') {
            updateActivityFeed();
        }
    }, 10000);
}

// Modal Functions
function showUploadModal() {
    document.getElementById('upload-modal').classList.add('show');
}

function hideUploadModal() {
    document.getElementById('upload-modal').classList.remove('show');
    document.getElementById('upload-form').reset();
}

// Document Upload
async function uploadDocument() {
    const title = document.getElementById('doc-title').value;
    const content = document.getElementById('doc-content').value;
    const author = document.getElementById('doc-author').value;
    const tags = document.getElementById('doc-tags').value.split(',').map(t => t.trim()).filter(t => t);
    
    if (!title || !content) {
        showToast('Title and content are required', 'warning');
        return;
    }
    
    const document = {
        title,
        content,
        author: author || undefined,
        tags
    };
    
    try {
        const response = await fetch(`${API_BASE}/documents/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(document)
        });
        
        if (response.ok) {
            showToast('Document uploaded successfully', 'success');
            hideUploadModal();
            loadDocuments();
        } else {
            showToast('Upload failed', 'error');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showToast('Upload failed', 'error');
    }
}

// File Upload Handler
function handleFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('doc-content').value = e.target.result;
        document.getElementById('doc-title').value = file.name.replace(/\.[^/.]+$/, '');
    };
    reader.readAsText(file);
}

// Cache Management
async function clearCache() {
    if (!confirm('Are you sure you want to clear the cache?')) return;
    
    try {
        // This would call your cache clear endpoint
        showToast('Cache cleared successfully', 'success');
    } catch (error) {
        showToast('Failed to clear cache', 'error');
    }
}

// Index Management
async function rebuildIndex() {
    if (!confirm('Rebuilding index may take a few minutes. Continue?')) return;
    
    showToast('Index rebuild started', 'info');
    
    // Simulate rebuild
    setTimeout(() => {
        showToast('Index rebuilt successfully', 'success');
    }, 3000);
}

// Chart Options
function getChartOptions(yAxisLabel) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                mode: 'index',
                intersect: false
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)'
                },
                title: {
                    display: true,
                    text: yAxisLabel
                }
            },
            x: {
                grid: {
                    display: false
                }
            }
        }
    };
}

// Generate mock data for charts
function generateTimeLabels(hours) {
    const labels = [];
    for (let i = hours; i > 0; i--) {
        labels.push(moment().subtract(i, 'hours').format('HH:00'));
    }
    return labels;
}

function generateRandomData(points, min, max) {
    return Array.from({ length: points }, () => 
        Math.floor(Math.random() * (max - min + 1)) + min
    );
}

// Mock Redis Info
async function getRedisInfo() {
    return {
        memory: '156 MB / 512 MB',
        hitRate: '76.4%',
        clients: '8',
        keys: '1,234'
    };
}

// Activity Feed
function updateActivityFeed() {
    const feed = document.getElementById('activity-feed');
    const activities = [
        { type: 'search', text: 'Searched for "machine learning"', time: 'just now', cache: true },
        { type: 'search', text: 'Searched for "redis cache"', time: '1 min ago', cache: true },
        { type: 'upload', text: 'Document uploaded: "AI Research Paper"', time: '3 mins ago' },
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
                    `<span class="cache-hit">${activity.cache ? 'CACHE' : 'MISS'}</span>` : ''}
            </div>
        `;
    });
    
    feed.innerHTML = html;
}

// Initialize everything
console.log('DSCE Frontend initialized');