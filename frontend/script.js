// API Configuration
const API_BASE_URL = 'http://localhost:8000/api/v1';
let searchVolumeChart = null;
let cachePerformanceChart = null;

// Navigation
document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const pageId = link.dataset.page;
        
        // Update active states
        document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
        link.classList.add('active');
        
        document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
        document.getElementById(`${pageId}-page`).classList.add('active');
        
        // Load page-specific data
        if (pageId === 'analytics') {
            loadAnalytics();
        } else if (pageId === 'status') {
            loadSystemStatus();
        }
    });
});

// Search functionality
async function performSearch(query, page = 0) {
    const resultsContainer = document.getElementById('results-list');
    const resultsHeader = document.getElementById('results-header');
    
    resultsContainer.innerHTML = '<div class="loading-spinner"></div>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/search/?q=${encodeURIComponent(query)}&limit=10&offset=${page * 10}`);
        const data = await response.json();
        
        if (data.results && data.results.length > 0) {
            resultsHeader.innerHTML = `Found ${data.total_results} results (${data.execution_time_ms.toFixed(2)}ms)`;
            renderResults(data.results);
            renderPagination(data.total_results, page, query);
        } else {
            resultsContainer.innerHTML = '<div class="no-results">No results found</div>';
        }
    } catch (error) {
        console.error('Search error:', error);
        resultsContainer.innerHTML = '<div class="error">Error performing search</div>';
    }
}

function renderResults(results) {
    const container = document.getElementById('results-list');
    container.innerHTML = '';
    
    results.forEach(result => {
        const card = document.createElement('div');
        card.className = 'result-card';
        
        const highlights = result.highlights ? 
            result.highlights.map(h => `<span class="highlight">${h}</span>`).join(' ') : '';
        
        card.innerHTML = `
            <h3 class="result-title">${result.document.title}</h3>
            <div class="result-snippet">${result.document.content.substring(0, 200)}...</div>
            <div class="result-meta">
                <span class="result-score">Relevance: ${(result.relevance_score * 100).toFixed(1)}%</span>
                <span>Author: ${result.document.author || 'Unknown'}</span>
                <span>Words: ${result.document.word_count}</span>
                <span>${highlights}</span>
            </div>
        `;
        
        container.appendChild(card);
    });
}

function renderPagination(total, currentPage, query) {
    const totalPages = Math.ceil(total / 10);
    const pagination = document.getElementById('pagination');
    
    pagination.innerHTML = '';
    
    for (let i = 0; i < totalPages; i++) {
        const btn = document.createElement('button');
        btn.className = `page-btn ${i === currentPage ? 'active' : ''}`;
        btn.textContent = i + 1;
        btn.addEventListener('click', () => performSearch(query, i));
        pagination.appendChild(btn);
    }
}

// Search suggestions
async function getSuggestions(query) {
    if (query.length < 2) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/search/suggest?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        const suggestionsContainer = document.getElementById('suggestions');
        if (data.suggestions && data.suggestions.length > 0) {
            suggestionsContainer.innerHTML = '';
            data.suggestions.forEach(suggestion => {
                const div = document.createElement('div');
                div.className = 'suggestion-item';
                div.textContent = suggestion;
                div.addEventListener('click', () => {
                    document.getElementById('search-input').value = suggestion;
                    suggestionsContainer.classList.remove('active');
                    performSearch(suggestion);
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

// Load analytics data
async function loadAnalytics() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats/`);
        const data = await response.json();
        
        // Update metrics
        document.getElementById('total-searches').textContent = data.total_searches.toLocaleString();
        document.getElementById('cache-hit-rate').textContent = `${(data.cache_hit_rate * 100).toFixed(1)}%`;
        document.getElementById('avg-response').textContent = `${data.avg_response_time_ms.toFixed(0)}ms`;
        document.getElementById('total-documents').textContent = data.total_documents.toLocaleString();
        
        // Update top queries table
        const tableBody = document.getElementById('top-queries-body');
        tableBody.innerHTML = '';
        
        data.top_queries.forEach(query => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${query.query}</td>
                <td>${query.count}</td>
                <td>${(data.avg_response_time_ms).toFixed(0)}ms</td>
                <td>${(data.cache_hit_rate * 100).toFixed(1)}%</td>
            `;
            tableBody.appendChild(row);
        });
        
        // Create charts
        createCharts(data);
        
    } catch (error) {
        console.error('Analytics error:', error);
    }
}

function createCharts(data) {
    // Search Volume Chart
    const searchCtx = document.getElementById('search-volume-chart').getContext('2d');
    
    if (searchVolumeChart) {
        searchVolumeChart.destroy();
    }
    
    searchVolumeChart = new Chart(searchCtx, {
        type: 'line',
        data: {
            labels: ['12am', '3am', '6am', '9am', '12pm', '3pm', '6pm', '9pm'],
            datasets: [{
                label: 'Search Volume',
                data: [65, 59, 80, 81, 156, 155, 140, 120],
                borderColor: '#ff9900',
                backgroundColor: 'rgba(255, 153, 0, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
    
    // Cache Performance Chart
    const cacheCtx = document.getElementById('cache-performance-chart').getContext('2d');
    
    if (cachePerformanceChart) {
        cachePerformanceChart.destroy();
    }
    
    cachePerformanceChart = new Chart(cacheCtx, {
        type: 'doughnut',
        data: {
            labels: ['Cache Hit', 'Cache Miss'],
            datasets: [{
                data: [
                    data.performance_metrics.cache_hits || 76,
                    data.performance_metrics.cache_misses || 24
                ],
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

// Load system status
async function loadSystemStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats/health`);
        const data = await response.json();
        
        // Update service statuses
        updateServiceStatus('api', data.services.api);
        updateServiceStatus('database', data.services.database);
        updateServiceStatus('redis', data.services.redis);
        
        // Load shard stats
        await loadShardStats();
        
    } catch (error) {
        console.error('Status error:', error);
    }
}

function updateServiceStatus(service, status) {
    const elements = {
        api: { uptime: 'api-uptime', requests: 'api-requests' },
        database: { connections: 'db-connections', latency: 'db-latency' },
        redis: { memory: 'redis-memory', hitRate: 'redis-hit-rate' }
    };
    
    // Update based on service type
    // This is simplified - you'd want to map actual data
}

async function loadShardStats() {
    const shardContainer = document.getElementById('shard-stats');
    shardContainer.innerHTML = '';
    
    const shards = ['A-F', 'G-M', 'N-Z'];
    shards.forEach(shard => {
        const div = document.createElement('div');
        div.className = 'status-metric';
        div.innerHTML = `
            <span>Shard ${shard}:</span>
            <span>${Math.floor(Math.random() * 500)} docs</span>
        `;
        shardContainer.appendChild(div);
    });
}

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Home page search
    const homeSearchBtn = document.getElementById('home-search-btn');
    const homeSearchInput = document.getElementById('home-search');
    
    if (homeSearchBtn && homeSearchInput) {
        homeSearchBtn.addEventListener('click', () => {
            const query = homeSearchInput.value.trim();
            if (query) {
                document.querySelector('[data-page="search"]').click();
                document.getElementById('search-input').value = query;
                performSearch(query);
            }
        });
        
        homeSearchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                homeSearchBtn.click();
            }
        });
    }
    
    // Search page
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('search-input');
    
    if (searchBtn && searchInput) {
        searchBtn.addEventListener('click', () => {
            const query = searchInput.value.trim();
            if (query) {
                performSearch(query);
            }
        });
        
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchBtn.click();
            }
        });
        
        // Search suggestions
        let suggestionTimeout;
        searchInput.addEventListener('input', () => {
            clearTimeout(suggestionTimeout);
            suggestionTimeout = setTimeout(() => {
                getSuggestions(searchInput.value);
            }, 300);
        });
        
        // Close suggestions on click outside
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target)) {
                document.getElementById('suggestions').classList.remove('active');
            }
        });
    }
    
    // Sort select
    const sortSelect = document.getElementById('sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', () => {
            const query = searchInput.value.trim();
            if (query) {
                performSearch(query);
            }
        });
    }
    
    // Load initial data
    loadQuickStats();
});

async function loadQuickStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats/`);
        const data = await response.json();
        
        document.getElementById('total-docs').textContent = data.total_documents.toLocaleString();
        document.getElementById('cache-rate').textContent = `${(data.cache_hit_rate * 100).toFixed(0)}%`;
        document.getElementById('avg-time').textContent = `${data.avg_response_time_ms.toFixed(0)}ms`;
    } catch (error) {
        console.error('Quick stats error:', error);
    }
}

// Sample dataset for testing
const sampleDocuments = [
    {
        title: "Introduction to Artificial Intelligence",
        content: "Artificial Intelligence (AI) is the simulation of human intelligence in machines that are programmed to think and learn. Machine learning is a subset of AI that enables systems to automatically learn and improve from experience.",
        author: "Dr. Sarah Johnson",
        tags: ["AI", "machine-learning", "technology"]
    },
    {
        title: "Distributed Systems Architecture",
        content: "Distributed systems consist of multiple computers that work together as a single system. Key concepts include scalability, fault tolerance, and consistency. Modern cloud applications are built on distributed system principles.",
        author: "Prof. Michael Chen",
        tags: ["distributed-systems", "architecture", "cloud"]
    },
    {
        title: "Redis Cache Best Practices",
        content: "Redis is an in-memory data structure store used as a database, cache, and message broker. It supports various data structures including strings, hashes, lists, sets, and sorted sets with range queries.",
        author: "Tech Team",
        tags: ["redis", "caching", "database"]
    },
    {
        title: "Natural Language Processing Fundamentals",
        content: "NLP combines computational linguistics with machine learning to process and analyze large amounts of natural language data. Applications include sentiment analysis, language translation, and chatbots.",
        author: "Dr. Emily Williams",
        tags: ["NLP", "AI", "linguistics"]
    },
    {
        title: "Scalable Search Engine Design",
        content: "Building scalable search engines requires understanding of inverted indices, relevance ranking, and distributed indexing. Systems like Elasticsearch and Solr implement these concepts for fast full-text search.",
        author: "James Anderson",
        tags: ["search", "scalability", "architecture"]
    }
];

// Function to load sample data
async function loadSampleData() {
    for (const doc of sampleDocuments) {
        try {
            const response = await fetch(`${API_BASE_URL}/documents/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(doc)
            });
            
            if (response.ok) {
                console.log(`Loaded document: ${doc.title}`);
            }
        } catch (error) {
            console.error(`Error loading document ${doc.title}:`, error);
        }
    }
}

// Export functions for use in console
window.loadSampleData = loadSampleData;
window.performSearch = performSearch;