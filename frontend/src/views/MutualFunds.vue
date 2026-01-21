<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import DonutChart from '@/components/DonutChart.vue'
import LineChart from '@/components/LineChart.vue'
import { financeApi, aiApi } from '@/api/client'
import { useNotificationStore } from '@/stores/notification'
import { 
    Search,
    Plus, 
    Upload, 
    RefreshCw,
    Lock,
    FileText,
    Eye,
    EyeOff,
    Mail,
    ChevronDown,
    Trash2
} from 'lucide-vue-next'
import { useCurrency } from '@/composables/useCurrency'
import { marked } from 'marked'

const notify = useNotificationStore()
const { formatAmount } = useCurrency()

const activeTab = ref('portfolio') // portfolio, search, import
const isLoading = ref(false)
const portfolio = ref<any[]>([])
const searchResults = ref<any[]>([])
const searchQuery = ref('')
const isSearching = ref(false)
const isAnalyzing = ref(false)
const aiAnalysis = ref('')
const currentUser = ref<any>(null)
const isNavLoading = ref(false)

const marketIndices = ref<{ name: string; value: string; change: string; percent: string; isUp: boolean; sparkline?: number[] }[]>([
    { name: 'NIFTY 50', value: 'Loading...', change: '0.00', percent: '0.00%', isUp: true },
    { name: 'SENSEX', value: 'Loading...', change: '0.00', percent: '0.00%', isUp: true },
    { name: 'BANK NIFTY', value: 'Loading...', change: '0.00', percent: '0.00%', isUp: true }
])

const searchFilters = ['All', 'Equity', 'Debt', 'Hybrid', 'Small Cap', 'Index', 'Bluechip', 'Technology', 'ELSS']
const activeFilter = ref('All')

// Sorting & Pagination
const sortBy = ref('relevance')
const sortOptions = [
    { label: 'Relevance', value: 'relevance' },
    { label: 'Returns (High to Low)', value: 'returns_desc' },
    { label: 'Returns (Low to High)', value: 'returns_asc' }
]
const searchOffset = ref(0)
const searchLimit = 20
const hasMoreResults = ref(true)
const isLoadingMore = ref(false)
const scrollSentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

const curatedFunds = [
    { schemeName: 'HDFC Index S&P BSE Sensex Fund', schemeCode: '119062', category: 'Index Fund', returns3Y: '24.5', rating: 5 },
    { schemeName: 'ICICI Prudential Bluechip Fund', schemeCode: '102594', category: 'Bluechip', returns3Y: '18.2', rating: 4 },
    { schemeName: 'SBI Small Cap Fund', schemeCode: '125497', category: 'Small Cap', returns3Y: '32.1', rating: 5 },
    { schemeName: 'Parag Parikh Flexi Cap Fund', schemeCode: '122639', category: 'Flexi Cap', returns3Y: '21.8', rating: 5 },
    { schemeName: 'Quant Infrastructure Fund', schemeCode: '120367', category: 'Sectoral', returns3Y: '28.4', rating: 4 }
]

const topAMCs = [
    { name: 'HDFC', query: 'HDFC Mutual Fund' },
    { name: 'SBI', query: 'SBI Mutual Fund' },
    { name: 'ICICI', query: 'ICICI Prudential' },
    { name: 'Axis', query: 'Axis Mutual Fund' },
    { name: 'Quant', query: 'Quant Mutual Fund' },
    { name: 'Nippon', query: 'Nippon India' }
]

// Transaction Form
const showTransactionModal = ref(false)
const selectedFund = ref<any>(null)
const transactionForm = ref({
    type: 'BUY',
    amount: 0,
    units: 0,
    nav: 0,
    date: new Date().toISOString().split('T')[0],
    folio_number: ''
})

// CAS Import
const fileInput = ref<HTMLInputElement | null>(null)
const casFile = ref<File | null>(null)
const casPassword = ref('')
const showCasPassword = ref(false)
const isPdfImporting = ref(false)
const isEmailImporting = ref(false)
const showImportSummary = ref(false)
const importStats = ref<any>(null)

// Helpers
function getRandomColor(str: string) {
    const colors = [
        '#6366f1', '#3b82f6', '#06b6d4', '#10b981', 
        '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'
    ]
    let hash = 0
    if (!str) return colors[0]
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash)
    }
    return colors[Math.abs(hash) % colors.length]
}

function getMockReturns(schemeCode: string | number) {
    const codeStr = String(schemeCode || '0')
    const hash = codeStr.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
    const base = 12 + (hash % 25)
    return base.toFixed(1)
}

// Stats
const portfolioStats = computed(() => {
    let invested = 0
    let current = 0
    portfolio.value.forEach(h => {
        invested += h.invested_value
        current += h.current_value
    })
    return {
        invested,
        current,
        pl: current - invested,
        plPercent: invested > 0 ? ((current - invested) / invested) * 100 : 0
    }
})

function generateSparklinePoints(data: number[], width: number, height: number): string {
    if (!data || data.length < 2) return ''
    
    const min = Math.min(...data)
    const max = Math.max(...data)
    const range = max - min || 1
    
    return data.map((value, index) => {
        const x = (index / (data.length - 1)) * width
        const y = height - ((value - min) / range) * height
        return `${x},${y}`
    }).join(' ')
}

async function fetchPortfolio() {
    isLoading.value = true
    try {
        const res = await financeApi.getPortfolio()
        portfolio.value = res.data
    } catch (e) {
        console.error(e)
        notify.error("Failed to load portfolio")
    } finally {
        isLoading.value = false
    }
}

const analytics = ref<any>(null)

async function fetchAnalytics() {
    try {
        const res = await financeApi.getAnalytics()
        analytics.value = res.data
    } catch (e) {
        console.error('Analytics fetch failed:', e)
    }
}

const performanceData = ref<any>(null)
const selectedPeriod = ref('3m')
const selectedGranularity = ref('1d') // Default to daily
const isLoadingTimeline = ref(false)

async function fetchPerformanceTimeline() {
    console.log('[Timeline] Starting fetch, isLoading:', isLoadingTimeline.value)
    isLoadingTimeline.value = true
    try {
        const res = await financeApi.getPerformanceTimeline(selectedPeriod.value, selectedGranularity.value)
        performanceData.value = res.data
        console.log('[Timeline] Data received:', res.data.timeline?.length, 'points')
    } catch (e) {
        console.error('Performance timeline fetch failed:', e)
    } finally {
        isLoadingTimeline.value = false
        console.log('[Timeline] Set loading to false:', isLoadingTimeline.value)
    }
}

async function clearCacheAndRefresh() {
    try {
        console.log('[Timeline] Clearing cache...')
        await financeApi.deleteCacheTimeline()
        notify.success("Timeline cache cleared. Recalculating...")
        console.log('[Timeline] Cache cleared, fetching fresh data...')
        await fetchPerformanceTimeline()
    } catch (e) {
        console.error('Failed to clear cache:', e)
        notify.error("Failed to clear timeline cache")
    }
}

async function cleanupDuplicates() {
    try {
        console.log('[Timeline] Cleaning up duplicates...')
        const res = await financeApi.cleanupDuplicateOrders()
        console.log('[Timeline] Cleanup complete:', res.data.message)
        notify.success(res.data.message)
        await clearCacheAndRefresh()
    } catch (e) {
        console.error('Failed to cleanup duplicates:', e)
        notify.error('Cleanup failed. See console for details.')
    }
}

const holdingToDelete = ref<any>(null)
const showDeleteConfirm = ref(false)

function confirmDelete(holding: any) {
    holdingToDelete.value = holding
    showDeleteConfirm.value = true
}

async function proceedDelete() {
    if (!holdingToDelete.value) return
    
    try {
        await financeApi.deleteHolding(holdingToDelete.value.id)
        notify.success("Holding removed successfully")
        showDeleteConfirm.value = false
        holdingToDelete.value = null
        await fetchPortfolio()
    } catch (error) {
        console.error("Delete failed", error)
        notify.error("Failed to delete holding")
        showDeleteConfirm.value = false
        holdingToDelete.value = null
    }
}

async function handleSearch() {
    if ((!searchQuery.value || searchQuery.value.length < 2) && activeFilter.value === 'All') return
    
    isSearching.value = true
    searchOffset.value = 0 // Reset pagination
    hasMoreResults.value = true
    
    try {
        const query = searchQuery.value.length >= 2 ? searchQuery.value : undefined
        const category = activeFilter.value !== 'All' ? activeFilter.value : undefined
        
        const response = await financeApi.searchFunds(query, category, undefined, searchLimit, 0, sortBy.value)
        
        searchResults.value = response.data.map((f: any) => ({
            ...f,
            category: f.schemeName.includes('Equity') ? 'Equity' : (f.schemeName.includes('Debt') ? 'Debt' : 'Hybrid'),
            returns3Y: getMockReturns(f.schemeCode)
        }))
        
        if (response.data.length < searchLimit) {
            hasMoreResults.value = false
        }
    } catch (error) {
        console.error('Search failed:', error)
        notify.error('Failed to search funds')
        searchResults.value = []
    } finally {
        isSearching.value = false
    }
}

async function loadMoreResults() {
    if (isLoadingMore.value || !hasMoreResults.value) return
    
    isLoadingMore.value = true
    searchOffset.value += searchLimit
    
    try {
        const query = searchQuery.value.length >= 2 ? searchQuery.value : undefined
        const category = activeFilter.value !== 'All' ? activeFilter.value : undefined
        
        const response = await financeApi.searchFunds(query, category, undefined, searchLimit, searchOffset.value, sortBy.value)
        
        if (response.data.length > 0) {
            const newFunds = response.data.map((f: any) => ({
                ...f,
                category: f.schemeName.includes('Equity') ? 'Equity' : (f.schemeName.includes('Debt') ? 'Debt' : 'Hybrid'),
                returns3Y: getMockReturns(f.schemeCode)
            }))
            searchResults.value = [...searchResults.value, ...newFunds]
            
            if (response.data.length < searchLimit) {
                hasMoreResults.value = false
            }
        } else {
            hasMoreResults.value = false
        }
    } catch (error) {
        notify.error('Failed to load more results')
    } finally {
        isLoadingMore.value = false
    }
}

async function searchByCategory(category: string) {
    searchQuery.value = ''
    activeFilter.value = category
    await handleSearch()
}

function openBuyModal(fund: any) {
    selectedFund.value = fund
    transactionForm.value = {
        type: 'BUY',
        amount: 0,
        units: 0,
        nav: 0, // Ideally fetch latest NAV here
        date: new Date().toISOString().split('T')[0],
        folio_number: ''
    }
    // Try to fetch latest NAV for this fund
    fetchLatestNav(fund.schemeCode)
    showTransactionModal.value = true
}

async function fetchLatestNav(code: string) {
    if (!code) return
    isNavLoading.value = true
    try {
        const res = await financeApi.getNav(code)
        if (res.data) {
            transactionForm.value.nav = res.data.nav
        }
    } catch (e) {
        console.warn("Could not fetch latest NAV")
    } finally {
        isNavLoading.value = false
    }
}

async function submitTransaction() {
    if (!selectedFund.value) return
    try {
        await financeApi.createFundTransaction({
            scheme_code: String(selectedFund.value.schemeCode),
            ...transactionForm.value,
            amount: Number(transactionForm.value.amount),
            units: Number(transactionForm.value.units),
            nav: Number(transactionForm.value.nav),
            date: new Date(transactionForm.value.date).toISOString()
        })
        notify.success("Transaction added")
        showTransactionModal.value = false
        activeTab.value = 'portfolio'
        fetchPortfolio()
        searchQuery.value = ''
        searchResults.value = []
    } catch (e) {
        notify.error("Failed to submit transaction")
    }
}

async function handleCasUpload() {
    if (!casFile.value) return
    isPdfImporting.value = true
    const formData = new FormData()
    formData.append('file', casFile.value)
    if (casPassword.value) formData.append('password', casPassword.value)

    try {
        // Reset stats and show modal loading state
        importStats.value = null
        showImportSummary.value = true
        
        const res = await financeApi.importCAS(formData)
        importStats.value = res.data
        fetchPortfolio()
    } catch (e: any) {
        notify.error(e.response?.data?.detail || "Import failed")
    } finally {
        isPdfImporting.value = false
    }
}

async function triggerEmailImport() {
    if (!casPassword.value) {
        notify.info("Please enter CAS password first")
        return
    }
    isEmailImporting.value = true
    // Reset stats and show modal loading state
    importStats.value = null
    showImportSummary.value = true

    try {
        const formData = new FormData()
        formData.append('password', casPassword.value)
        const res = await financeApi.importCASEmail(formData)
        
        const stats = res.data.stats
        if (stats.found > 0) {
            importStats.value = {
                status: 'success',
                processed: stats.processed,
                total_found: stats.found,
                details: { failed: stats.errors?.map((e: string) => ({ error: e, scheme_name: 'Email Error', amount: 0, date: new Date() })) || [] }
            }
            showImportSummary.value = true
            fetchPortfolio()
        } else {
            notify.info("No CAS emails found")
        }
    } catch (e) {
        notify.error("Email import failed")
    } finally {
        isEmailImporting.value = false
    }
}

async function generateAIAnalysis() {
    isAnalyzing.value = true
    try {
        const summary = {
            total_invested: portfolioStats.value.invested,
            current_value: portfolioStats.value.current,
            total_holdings: portfolio.value.length,
            holdings: portfolio.value.map(h => ({
                name: h.scheme_name,
                invested: h.invested_value,
                pnl_percent: ((h.current_value - h.invested_value) / h.invested_value) * 100,
                category: h.category || 'Unknown'
            }))
        }
        
        const res = await aiApi.generateSummaryInsights(summary)
        if (res.data && res.data.insights) {
             aiAnalysis.value = res.data.insights
        } else {
             aiAnalysis.value = "AI could not generate insights at this time."
        }
    } catch (error) {
        notify.error("Failed to generate analysis")
        aiAnalysis.value = "Failed to communicate with AI service."
    } finally {
        isAnalyzing.value = false
    }
}

function handleFileSelect(event: any) {
    const file = event.target.files[0]
    if (file) casFile.value = file
}

onMounted(async () => {
    fetchPortfolio()
    try {
        const res = await financeApi.getMe()
        currentUser.value = res.data
        
        // Initial Load
        await Promise.all([
            fetchUniqueParams(),
            handleSearch(),
            fetchMarketIndices(),
            fetchAnalytics(),
            fetchPerformanceTimeline()
        ])
        
        // Auto-generate password if available and currently empty
        if (currentUser.value?.pan_number && !casPassword.value) {
            casPassword.value = currentUser.value.pan_number.toUpperCase()
        }
    } catch (e) {
        console.error("Failed to fetch user profile", e)
    }
})

async function fetchMarketIndices() {
    try {
        const res = await financeApi.getMarketIndices()
        if (res.data && res.data.length > 0) {
            marketIndices.value = res.data
        } else {
             marketIndices.value = [
                { name: 'NIFTY 50', value: 'Unavailable', change: '0.00', percent: '0.00%', isUp: true },
                { name: 'SENSEX', value: 'Unavailable', change: '0.00', percent: '0.00%', isUp: true },
                { name: 'BANK NIFTY', value: 'Unavailable', change: '0.00', percent: '0.00%', isUp: true }
             ]
        }
    } catch (error) {
         console.error('Failed to fetch indices:', error)
         marketIndices.value = [
            { name: 'NIFTY 50', value: 'Error', change: '0.00', percent: '0.00%', isUp: true },
            { name: 'SENSEX', value: 'Error', change: '0.00', percent: '0.00%', isUp: true },
            { name: 'BANK NIFTY', value: 'Error', change: '0.00', percent: '0.00%', isUp: true }
         ]
    }
}

async function fetchUniqueParams() {
    // Placeholder for future unique parameters fetching
    return Promise.resolve()
}

// Correctly watch for sentinel availability
watch(scrollSentinel, (el) => {
    if (el) {
        if (!observer) {
            observer = new IntersectionObserver((entries) => {
                if (entries[0].isIntersecting && !isLoadingMore.value && hasMoreResults.value) {
                    loadMoreResults()
                }
            }, {
                root: null,
                threshold: 0.1,
                rootMargin: '100px'
            })
        }
        observer.observe(el)
    }
})

onUnmounted(() => {
    if (observer) observer.disconnect()
})

// Functional Filters Logic
watch(activeFilter, (newFilter) => {
    if (newFilter === 'All') {
        if (!searchQuery.value) {
            searchResults.value = []
        } else {
            handleSearch()
        }
    } else {
        searchByCategory(newFilter)
    }
})

// Watch for period changes
watch(selectedPeriod, (newPeriod) => {
    // Default logic: 3 Months -> Daily, others can stay as is or default to Weekly
    if (newPeriod === '3m') {
        selectedGranularity.value = '1d'
    } else if (newPeriod === '1m') {
        selectedGranularity.value = '1d'
    } else {
        selectedGranularity.value = '1w'
    }
    fetchPerformanceTimeline()
})

watch(selectedGranularity, () => {
    fetchPerformanceTimeline()
})

function getSparklinePath(points: number[]): string {
    if (!points || points.length < 2) return ''
    const width = 60
    const height = 16 // Minimal height
    const min = Math.min(...points)
    const max = Math.max(...points)
    const range = max - min || 1
    
    // Normalize points to fit SVG viewbox 0 0 width height
    // Step X
    const stepX = width / (points.length - 1)
    
    const path = points.map((p, i) => {
        const x = i * stepX
        // Invert Y axis for SVG (0 is top)
        const y = height - ((p - min) / range) * height
        return `${i === 0 ? 'M' : 'L'} ${x},${y}`
    }).join(' ')
    
    return path
}
</script>

<template>
    <MainLayout>
        <div class="page-header">
            <div class="header-left">
                <h1 class="page-title">Mutual Funds</h1>
                <div class="header-tabs">
                    <button 
                        class="tab-btn" 
                        :class="{ active: activeTab === 'portfolio' }"
                        @click="activeTab = 'portfolio'"
                    >
                        Portfolio
                    </button>
                    <button 
                        class="tab-btn" 
                        :class="{ active: activeTab === 'search' }"
                        @click="activeTab = 'search'"
                    >
                        Search & Add
                    </button>
                    <button 
                        class="tab-btn" 
                        :class="{ active: activeTab === 'import' }"
                        @click="activeTab = 'import'"
                    >
                        Import CAS
                    </button>
                </div>

                <span class="transaction-count ml-4">{{ portfolio.length }} funds</span>
            </div>
            <div class="header-actions">
                <button v-if="activeTab === 'portfolio'" @click="fetchPortfolio" class="btn-premium-secondary" :disabled="isLoading">
                    <RefreshCw :size="16" :class="{ 'spin': isLoading }" />
                    <span>Refresh</span>
                </button>
                <button v-if="activeTab === 'portfolio'" @click="activeTab = 'search'" class="btn-premium-primary">
                    <div class="btn-glow"></div>
                    <Plus :size="16" />
                    <span>New Investment</span>
                </button>
            </div>
        </div>

        <div class="content-container anim-fade-in">
            <!-- PORTFOLIO TAB -->
            <div v-if="activeTab === 'portfolio'" class="analytics-layout">
                <!-- AI Card (Standard from Insights.vue) -->
                <div class="ai-card" :class="{ 'is-loading': isAnalyzing }">
                    <div class="ai-card-content">
                        <div class="ai-header">
                            <div class="ai-title-left">
                                <div class="ai-sparkle-icon">✨</div>
                                <div class="ai-title-group">
                                    <h3 class="ai-card-title">Portfolio Intelligence</h3>
                                    <p class="ai-card-subtitle">AI analysis of holdings, sector risk, and performance</p>
                                </div>
                            </div>
                            <button 
                                @click="generateAIAnalysis"
                                :disabled="isAnalyzing"
                                class="ai-btn-glass"
                            >
                                <svg v-if="!isAnalyzing" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/><path d="M9 12l2 2 4-4"/></svg>
                                {{ isAnalyzing ? 'Analyzing...' : 'Refresh Analysis' }}
                            </button>
                        </div>
                        
                        <div v-if="aiAnalysis" class="ai-insight-box custom-scrollbar">
                            <div class="ai-insight-text markdown-body" v-html="marked(aiAnalysis)"></div>
                        </div>
                        <div v-else-if="isAnalyzing" class="ai-loading-skeleton">
                            <div class="shimmer-line"></div>
                            <div class="shimmer-line w-3/4"></div>
                            <div class="shimmer-line w-1/2"></div>
                        </div>
                        <p v-else class="ai-card-description">
                            Let AI analyze your asset allocation and sector exposure to suggest optimal rebalancing strategies.
                        </p>
                    </div>
                    <!-- Standard Mesh Blobs -->
                    <div class="mesh-blob blob-1"></div>
                    <div class="mesh-blob blob-2"></div>
                    <div class="mesh-blob blob-3"></div>
                </div>

                <!-- Standard Summary Cards -->
                <div class="summary-cards">
                    <div class="summary-card income">
                        <div class="card-icon">💰</div>
                        <div class="card-content">
                            <span class="card-label">Current Value</span>
                            <span class="card-value">{{ formatAmount(portfolioStats.current) }}</span>
                            <span class="card-trend text-emerald-600">
                                {{ portfolioStats.pl >= 0 ? '↑' : '↓' }} {{ Math.abs(portfolioStats.plPercent).toFixed(2) }}% Returns
                            </span>
                        </div>
                    </div>
                    <div class="summary-card net">
                        <div class="card-icon">📥</div>
                        <div class="card-content">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                <span class="card-label">Invested Amount</span>
                                <button 
                                    @click="cleanupDuplicates" 
                                    class="btn-ghost" 
                                    style="padding: 2px 6px; font-size: 10px; color: #94a3b8; border: 1px solid #e2e8f0; border-radius: 4px; cursor: pointer;"
                                    title="Cleanup duplicate transactions and sync data"
                                >Fix Data</button>
                            </div>
                            <span class="card-value">{{ formatAmount(portfolioStats.invested) }}</span>
                            <span class="card-trend text-indigo-600"> Across {{ portfolio.length }} Funds</span>
                        </div>
                    </div>
                    <div class="summary-card" :class="portfolioStats.pl >= 0 ? 'income' : 'expense'">
                        <div class="card-icon">📈</div>
                        <div class="card-content">
                            <span class="card-label">Overall Profit/Loss</span>
                            <span class="card-value" :class="portfolioStats.pl >= 0 ? 'text-emerald-700' : 'text-rose-700'">
                                {{ portfolioStats.pl >= 0 ? '+' : '' }}{{ formatAmount(portfolioStats.pl) }}
                            </span>
                             <span class="card-trend" :class="analytics && analytics.xirr !== null && analytics.xirr >= 0 ? 'text-emerald-600' : 'text-rose-600'">
                                {{ analytics && analytics.xirr !== null ? `${analytics.xirr.toFixed(2)}% XIRR` : 'XIRR: N/A' }}
                             </span>
                        </div>
                    </div>
                </div>

                <!-- Holdings List (Standard Table) -->
                <div class="analytics-card full-width">
                     <div class="card-header-flex">
                        <h3 class="card-title">Portfolio Holdings</h3>
                        <div class="card-controls">
                             <!-- Optional controls here -->
                        </div>
                    </div>
                    
                    <div class="table-container">
                         <div v-if="portfolio.length === 0 && !isLoading" class="py-12 text-center">
                            <div class="text-4xl mb-3">🌱</div>
                            <h3 class="text-gray-900 font-bold">No investments found</h3>
                            <p class="text-gray-500 text-sm">Add funds or import CAS to start tracking.</p>
                        </div>
                        
                        <table v-else class="modern-table">
                            <thead>
                                <tr>
                                    <th style="width: 35%">Fund Name</th>
                                    <th>Units</th>
                                    <th>Avg Price</th>
                                    <th>Current NAV</th>
                                    <th class="tabular-nums">Invested</th>
                                    <th class="tabular-nums">Current Value</th>
                                    <th>Returns</th>
                                    <th style="width: 140px"></th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="holding in portfolio" :key="holding.id">
                                    <td style="position: relative;">
                                        <!-- Color Accent Bar -->
                                        <div style="position: absolute; left: 0; top: 0; bottom: 0; width: 3px; border-radius: 0 4px 4px 0;" 
                                             :style="{ background: getRandomColor(holding.scheme_name) }"></div>
                                        <div style="padding-left: 1rem;">
                                                <div class="font-medium text-gray-900 line-clamp-1" :title="holding.scheme_name">{{ holding.scheme_name }}</div>
                                                <div style="display: flex; align-items: center; gap: 0.375rem; margin-top: 0.25rem;">
                                                    <span style="display: inline-flex; align-items: center; padding: 0.125rem 0.5rem; border-radius: 9999px; font-size: 10px; font-weight: 600; background-color: #f1f5f9; color: #334155;">
                                                        {{ holding.folio_number || 'No Folio' }}
                                                    </span>
                                                    <span style="display: inline-flex; align-items: center; padding: 0.125rem 0.5rem; border-radius: 9999px; font-size: 10px; font-weight: 600; background-color: #e0e7ff; color: #4338ca; font-family: monospace;">
                                                        {{ holding.scheme_code }}
                                                    </span>
                                                    <!-- 30-Day NAV Sparkline -->
                                                    <svg v-if="holding.sparkline && holding.sparkline.length > 1" width="50" height="16" style="margin-left: 0.25rem;">
                                                        <polyline 
                                                            :points="generateSparklinePoints(holding.sparkline, 50, 16)" 
                                                            fill="none" 
                                                            :stroke="holding.profit_loss >= 0 ? '#10b981' : '#ef4444'" 
                                                            stroke-width="1.5"
                                                            stroke-linecap="round"
                                                            stroke-linejoin="round"
                                                        />
                                                    </svg>
                                                </div>
                                        </div>
                                    </td>
                                    <td class="tabular-nums font-medium text-gray-700">{{ holding.units.toFixed(3) }}</td>
                                    <td class="tabular-nums text-gray-500">{{ formatAmount(holding.average_price) }}</td>
                                    <td class="tabular-nums">
                                        <div class="text-gray-900 font-medium">{{ formatAmount(holding.last_nav) }}</div>
                                        <div class="text-[9px] text-gray-400 font-medium">{{ holding.last_updated }}</div>
                                    </td>
                                    <td class="tabular-nums font-medium text-gray-700">{{ formatAmount(holding.invested_value) }}</td>
                                    <td class="tabular-nums font-bold text-gray-900">{{ formatAmount(holding.current_value) }}</td>
                                    <td>
                                        <div :class="holding.profit_loss >= 0 ? 'text-emerald-600' : 'text-rose-600'">
                                            <div class="font-bold text-xs">{{ holding.profit_loss >= 0 ? '+' : '' }}{{ formatAmount(holding.profit_loss) }}</div>
                                            <div class="text-[10px] opacity-80 font-bold">
                                                {{ ((holding.profit_loss / (holding.invested_value || 1)) * 100).toFixed(2) }}%
                                            </div>
                                        </div>
                                    </td>
                                    <td style="white-space: nowrap; padding-left: 0.5rem; padding-right: 0.5rem;">
                                        <div class="flex items-center justify-end gap-2 flex-nowrap">
                                            <button class="icon-btn text-rose-500 hover:text-rose-700 hover:bg-rose-50 border-rose-100" @click="confirmDelete(holding)" title="Remove Holding">
                                                <Trash2 :size="14" />
                                            </button>
                                            <button class="icon-btn" @click="openBuyModal(holding)" title="Add Transaction">
                                                <Plus :size="14" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Portfolio Analytics Section (Only in Portfolio Tab) -->
            <div v-if="activeTab === 'portfolio' && analytics && portfolio.length > 0" class="analytics-section">
                <h3 class="section-title">Portfolio Analytics</h3>
                
                <!-- Performance Timeline Chart (Full Width) -->
                <div class="analytics-card performance-card" style="grid-column: 1 / -1;">
                    <div class="card-header-flex" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                        <h4 class="card-header" style="margin: 0;">Performance Timeline</h4>
                        <div style="display: flex; gap: 0.75rem; align-items: center;">
                            <!-- Granularity Selector -->
                            <div class="granularity-selector" style="display: flex; gap: 0.25rem; align-items: center; background: #f8fafc; padding: 2px; border-radius: 6px; border: 1px solid #e2e8f0;">
                                <select 
                                    v-model="selectedGranularity"
                                    style="border: none; background: transparent; font-size: 11px; font-weight: 600; color: #64748b; padding: 2px 4px; outline: none; cursor: pointer;"
                                >
                                    <option value="1d">Daily</option>
                                    <option value="1w">Weekly</option>
                                    <option value="1m">Monthly</option>
                                </select>
                            </div>

                            <div class="period-selector" style="display: flex; gap: 0.5rem;">
                                <button 
                                    v-for="p in ['1m', '3m', '6m', '1y', 'all']"
                                    :key="p"
                                    :class="{active: selectedPeriod === p}"
                                    @click="selectedPeriod = p"
                                    style="padding: 0.375rem 0.75rem; border-radius: 6px; border: 1px solid #e2e8f0; background: white; cursor: pointer; font-size: 0.875rem; font-weight: 500; transition: all 0.2s;"
                                    :style="{
                                        background: selectedPeriod === p ? '#3b82f6' : 'white',
                                        color: selectedPeriod === p ? 'white' : '#64748b',
                                        borderColor: selectedPeriod === p ? '#3b82f6' : '#e2e8f0'
                                    }"
                                >{{ p.toUpperCase() }}</button>
                            </div>
                            <button 
                                @click="clearCacheAndRefresh"
                                style="padding: 0.375rem 0.75rem; border-radius: 6px; border: 1px solid #e2e8f0; background: white; cursor: pointer; font-size: 0.875rem; font-weight: 500; transition: all 0.2s; display: flex; align-items: center; gap: 0.375rem;"
                                title="Clear cache and recalculate"
                            >
                                <RefreshCw :size="14" />
                                <span>Refresh</span>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Loading State -->
                    <div v-if="isLoadingTimeline" style="position: relative; min-height: 320px;">
                        <div style="position: absolute; inset: 0; background: rgba(255, 255, 255, 0.95); display: flex; align-items: center; justify-content: center; border-radius: 8px; z-index: 10; border: 2px dashed #cbd5e1;">
                            <div style="display: flex; flex-direction: column; align-items: center; gap: 0.75rem;">
                                <div class="spinner" style="width: 40px; height: 40px; border: 4px solid #e2e8f0; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite;"></div>
                                <span style="color: #475569; font-size: 0.9375rem; font-weight: 500;">Loading performance data...</span>
                            </div>
                        </div>
                        <!-- Show faded chart if exists -->
                        <div v-if="performanceData?.timeline" style="opacity: 0.2; pointer-events: none;">
                            <LineChart 
                                :data="performanceData.timeline" 
                                :benchmark="performanceData.benchmark"
                                :height="280" 
                            />
                        </div>
                    </div>
                    
                    <!-- Chart (Not Loading) -->
                    <div v-else-if="performanceData?.timeline && performanceData.timeline.length > 0">
                        <LineChart 
                            :data="performanceData.timeline" 
                            :benchmark="performanceData.benchmark"
                            :height="280" 
                        />
                    </div>
                    
                    <!-- Empty State -->
                    <div v-else style="text-align: center; padding: 3rem; color: #94a3b8;">
                        No performance data available
                    </div>
                </div>
                
                <div class="analytics-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; margin-top: 1.5rem;">
                    <!-- Asset Allocation Donut Chart -->
                    <div class="analytics-card allocation-card">
                        <h4 class="card-header">Asset Allocation</h4>
                        <DonutChart :data="analytics.asset_allocation" :size="180" />
                    </div>

                    <!-- Sector/Category Distribution -->
                    <div class="analytics-card allocation-card">
                        <h4 class="card-header">Sector / Category Distribution</h4>
                        <DonutChart :data="analytics.category_allocation || {}" :size="180" />
                    </div>
                </div>

                <div class="analytics-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; margin-top: 1.5rem;">
                    <!-- Top Gainers -->
                    <div class="analytics-card performers-card">
                        <h4 class="card-header gainers">🚀 Top Gainers</h4>
                        <div class="performers-list">
                            <div v-for="fund in analytics.top_gainers" :key="fund.id" class="performer-item">
                                <div class="performer-left">
                                    <div class="performer-name">{{ fund.scheme_name }}</div>
                                    <div class="performer-code">{{ fund.scheme_code }}</div>
                                </div>
                                <div class="performer-right positive">
                                    <div class="performer-pl">+{{ formatAmount(fund.profit_loss) }}</div>
                                    <div class="performer-percent">+{{ fund.pl_percent.toFixed(2) }}%</div>
                                </div>
                            </div>
                            <div v-if="analytics.top_gainers.length === 0" class="empty-state">
                                No gainers yet
                            </div>
                        </div>
                    </div>
                    
                    <!-- Top Losers -->
                    <div class="analytics-card performers-card">
                        <h4 class="card-header losers">📉 Top Losers</h4>
                        <div class="performers-list">
                            <div v-for="fund in analytics.top_losers" :key="fund.id" class="performer-item">
                                <div class="performer-left">
                                    <div class="performer-name">{{ fund.scheme_name }}</div>
                                    <div class="performer-code">{{ fund.scheme_code }}</div>
                                </div>
                                <div class="performer-right negative">
                                    <div class="performer-pl">{{ formatAmount(fund.profit_loss) }}</div>
                                    <div class="performer-percent">{{ fund.pl_percent.toFixed(2) }}%</div>
                                </div>
                            </div>
                            <div v-if="analytics.top_losers.length === 0" class="empty-state">
                                No losers
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- SEARCH TAB (Consolidated & Full Width) -->
            <div v-if="activeTab === 'search'" class="search-tab-wrapper full-width animate-in">
                <!-- All controls in one row: Filters, Search, Sort -->
                <div style="display: flex; gap: 1rem; align-items: center; margin-bottom: 2rem; flex-wrap: wrap;">
                    <!-- Category Filter Chips -->
                    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; flex: 1; min-width: 200px;">
                        <button 
                            v-for="filter in searchFilters" 
                            :key="filter"
                            class="filter-chip"
                            :class="{ active: activeFilter === filter }"
                            @click="activeFilter = filter"
                        >
                            {{ filter }}
                        </button>
                    </div>
                    
                    <!-- Search Input -->
                    <div class="filter-search-input-wrapper" style="flex: 0 1 300px; min-width: 200px;">
                        <Search :size="16" class="filter-search-icon" />
                        <input 
                            v-model="searchQuery" 
                            @keyup.enter="handleSearch"
                            placeholder="Search by fund name or AMC..." 
                            type="text"
                            class="filter-search-input"
                        />
                    </div>

                    <!-- Sort Dropdown -->
                    <div class="sort-dropdown-container" style="min-width: 150px;">
                        <select v-model="sortBy" @change="handleSearch" class="sort-select">
                            <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">
                                {{ opt.label }}
                            </option>
                        </select>
                        <ChevronDown :size="14" class="sort-icon" />
                    </div>

                    <!-- Search Button -->
                    <button 
                        class="filter-search-btn"
                        @click="handleSearch"
                        :disabled="isSearching"
                        style="min-width: 100px;"
                    >
                        <RefreshCw v-if="isSearching" :size="14" class="spin" />
                        <span v-else>Search</span>
                    </button>
                </div>

                <!-- SEARCH RESULTS -->
                <div v-if="isSearching" class="search-loading-state">
                    <div class="loader-glass">
                        <RefreshCw :size="32" class="spin mb-4" />
                        <p>Finding the best funds for you...</p>
                    </div>
                </div>

                <div v-else-if="searchResults.length > 0" class="search-results-grid-premium">
                    <div 
                        v-for="(fund, index) in searchResults" 
                        :key="fund.schemeCode" 
                        class="fund-glass-card" 
                        @click="openBuyModal(fund)"
                        :style="{ animationDelay: `${index * 50}ms` }"
                    >
                        <div class="fund-card-inner">
                            <div class="fund-card-top">
                                <div class="fund-icon-box" :style="{ background: getRandomColor(fund.schemeName) }">
                                    {{ fund.schemeName[0] }}
                                </div>
                                <div class="fund-meta-badges">
                                    <span class="amfi-badge">{{ fund.schemeCode }}</span>
                                    <span class="direct-badge">Direct • Growth</span>
                                </div>
                            </div>
                            
                            <div class="fund-card-body">
                                <h3>{{ fund.schemeName }}</h3>
                            </div>

                            <div class="fund-stats-row mb-4">
                                <div class="stat-item">
                                    <label>Returns (3Y)</label>
                                    <span class="text-emerald-600 font-bold">+{{ getMockReturns(fund.schemeCode) }}%</span>
                                </div>
                                <div class="stat-item">
                                    <label>Rating</label>
                                    <span class="text-amber-500">★★★★☆</span>
                                </div>
                            </div>
                            
                            <div class="fund-card-footer">
                                <div class="fund-action-indicator">
                                    <span>Invest Now</span>
                                    <Plus :size="14" />
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Load More Trigger / Sentinel -->
                    <div v-if="hasMoreResults && !isSearching" ref="scrollSentinel" class="load-more-container">
                        <div class="loader-glass-mini" v-if="isLoadingMore">
                            <RefreshCw :size="20" class="spin" />
                            <span>Loading more funds...</span>
                        </div>
                         <!-- Fallback button if observer fails or purely for manual control if needed (hidden for now essentially) -->
                        <button v-else @click="loadMoreResults" class="load-more-btn">
                            Load More
                        </button>
                    </div>
                </div>
                <div v-else-if="!isSearching && searchQuery" class="empty-state-search">
                    <div class="empty-glass-icon">🔍</div>
                    <h2>No matching funds</h2>
                    <p>We couldn't find any funds matching "{{ searchQuery }}". Try searching for AMFI codes or part of the scheme name.</p>
                </div>
                
                <div v-else-if="!isSearching && !searchQuery" class="search-discovery-section animate-slide-up">
                    
                    <!-- Market Pulse Hero -->
                    <div class="market-pulse-hero mb-10">
                        <div class="pulse-header">
                            <h3>Market Pulse</h3>
                            <span class="live-indicator"><span class="blink">●</span> Live</span>
                        </div>
                        <div class="indices-grid">
                            <div v-for="idx in marketIndices" :key="idx.name" class="index-card">
                                <div class="index-card-header">
                                    <div>
                                        <div class="index-name">{{ idx.name }}</div>
                                        <div class="index-val">{{ idx.value }}</div>
                                    </div>
                                    <div class="index-sparkline" v-if="idx.sparkline && idx.sparkline.length > 0">
                                         <svg width="60" height="20" viewBox="0 0 60 20" fill="none">
                                            <path 
                                                :d="getSparklinePath(idx.sparkline)" 
                                                stroke-width="1.5" 
                                                :stroke="idx.isUp ? '#10b981' : '#f43f5e'"
                                                stroke-linecap="round"
                                                stroke-linejoin="round"
                                            />
                                         </svg>
                                    </div>
                                </div>
                                <div class="index-change" :class="idx.isUp ? 'text-emerald-400' : 'text-rose-400'">
                                    {{ idx.change }} ({{ idx.percent }})
                                </div>
                            </div>
                        </div>
                    </div>


                    <div class="discovery-header mt-12">
                        <div class="header-line"></div>
                        <span>Trending Funds</span>
                        <div class="header-line"></div>
                    </div>

                    <div class="trending-funds-grid-premium">
                        <div 
                            v-for="fund in curatedFunds" 
                            :key="fund.schemeCode"
                            class="trending-card-premium"
                            @click="openBuyModal(fund)"
                        >
                            <div class="trending-card-top">
                                <div class="trending-icon" :style="{ background: getRandomColor(fund.schemeName) }">
                                    {{ fund.schemeName[0] }}
                                </div>
                                <div class="trending-badges">
                                    <span class="trend-badge">Top Rated</span>
                                </div>
                            </div>
                            
                            <h4>{{ fund.schemeName }}</h4>
                            
                            <div class="trending-metrics">
                                <div class="metric">
                                    <span class="label">3Y Return</span>
                                    <span class="value text-emerald-600">+{{ fund.returns3Y }}%</span>
                                </div>
                                <div class="metric">
                                    <span class="label">Category</span>
                                    <span class="value">{{ fund.category }}</span>
                                </div>
                            </div>

                            <button class="trending-action-btn">
                                Invest Now <Plus :size="14" />
                            </button>
                        </div>
                    </div>

                    <div class="discovery-header mt-12">
                        <div class="header-line"></div>
                        <span>Top AMCs</span>
                        <div class="header-line"></div>
                    </div>

                    <div class="amc-grid">
                        <button 
                            v-for="amc in topAMCs" 
                            :key="amc.name" 
                            class="amc-chip"
                            @click="searchByCategory(amc.query)"
                        >
                            {{ amc.name }}
                        </button>
                    </div>
                </div>
            </div>

            <!-- IMPORT TAB (Side-by-Side Premium Redesign) -->
            <div v-if="activeTab === 'import'" class="import-tab-content animate-in">
                <div class="import-grid-premium">
                    <!-- PDF UPLOAD CARD -->
                    <div class="glass-import-card">
                        <div class="mode-header">
                            <div class="icon-box-premium indigo">
                                <Upload :size="28" />
                            </div>
                            <h2>PDF Statement</h2>
                            <p>Upload your CAS PDF from CAMS or KFintech.</p>
                        </div>

                        <div 
                            class="upload-zone-premium"
                            @click="fileInput?.click()"
                            :class="{ 'has-file': casFile }"
                        >
                            <input type="file" ref="fileInput" @change="handleFileSelect" accept=".pdf" hidden />
                            <div v-if="casFile" class="upload-file-info animate-fade">
                                <div class="file-icon-wrapper">
                                    <FileText :size="32" />
                                    <div class="file-check">✓</div>
                                </div>
                                <div class="text-lg font-bold text-gray-900 mt-2 truncate w-full px-4">{{ casFile.name }}</div>
                            </div>
                            <div v-else class="upload-placeholder">
                                <div class="upload-icon-circle">
                                    <Upload :size="24" />
                                </div>
                                <div class="upload-text">Browse CAS PDF</div>
                            </div>
                            <!-- Mesh Accents -->
                            <div class="upload-mesh mesh-1"></div>
                        </div>

                        <div class="password-field-group mt-6">
                            <label class="field-label">PDF Password</label>
                            <div class="premium-input-group">
                                <Lock :size="16" class="input-icon-leading" />
                                <input 
                                    :type="showCasPassword ? 'text' : 'password'" 
                                    v-model="casPassword" 
                                    placeholder="e.g. PAN Number" 
                                    class="clean-input" 
                                />
                                <button 
                                    type="button"
                                    class="password-toggle-btn"
                                    @click="showCasPassword = !showCasPassword"
                                >
                                    <Eye v-if="!showCasPassword" :size="18" />
                                    <EyeOff v-else :size="18" />
                                </button>
                            </div>
                        </div>

                        <div class="action-footer mt-auto pt-6">
                             <button 
                                class="btn-primary-large w-full" 
                                @click="handleCasUpload" 
                                :disabled="!casFile || isPdfImporting || isEmailImporting"
                            >
                                <RefreshCw v-if="isPdfImporting" :size="18" class="spin mr-2" />
                                {{ isPdfImporting ? 'Processing...' : 'Unlock & Import' }}
                            </button>
                        </div>
                    </div>

                    <!-- EMAIL SYNC CARD -->
                    <div class="glass-import-card">
                         <div class="mode-header">
                            <div class="icon-box-premium emerald">
                                <Mail :size="28" />
                            </div>
                            <h2>Email Sync</h2>
                            <p>Scan linked email accounts for recent CAS.</p>
                        </div>

                        <div class="info-box-premium emerald mb-6">
                            <h4>How it works</h4>
                            <p>We securely search for recent emails and process the attachments using the password provided below.</p>
                        </div>
                        
                        <div class="password-field-group mb-6">
                            <label class="field-label">Sync Password</label>
                             <div class="premium-input-group">
                                <Lock :size="16" class="input-icon-leading" />
                                <input 
                                    :type="showCasPassword ? 'text' : 'password'" 
                                    v-model="casPassword" 
                                    placeholder="Enter PDF password" 
                                    class="clean-input" 
                                />
                                <button 
                                    type="button"
                                    class="password-toggle-btn"
                                    @click="showCasPassword = !showCasPassword"
                                >
                                    <Eye v-if="!showCasPassword" :size="18" />
                                    <EyeOff v-else :size="18" />
                                </button>
                            </div>
                        </div>

                        <div class="action-footer mt-auto">
                            <button class="btn-primary-large emerald-theme w-full" @click="triggerEmailImport" :disabled="isEmailImporting || isPdfImporting">
                                <RefreshCw v-if="isEmailImporting" :size="18" class="spin mr-2" />
                                <span v-else class="mr-2">📧</span>
                                {{ isEmailImporting ? 'Scanning...' : 'Scan My Inbox' }}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- TRANSACTIONS MODAL -->
        <div v-if="showTransactionModal" class="modal-overlay" @click.self="showTransactionModal = false">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Record Transaction</h2>
                    <button class="close-btn" @click="showTransactionModal = false">✕</button>
                </div>
                
                <div class="p-4 bg-slate-50 border border-slate-100 flex items-center gap-4 rounded-2xl mb-8">
                    <div class="w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold text-lg shadow-sm"
                         :style="{ background: getRandomColor(selectedFund?.schemeName || selectedFund?.scheme_name) }">
                        {{ (selectedFund?.schemeName || selectedFund?.scheme_name)?.[0] }}
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="text-xs font-bold text-indigo-600 uppercase tracking-wider mb-0.5">Fund Name</div>
                        <div class="text-sm font-bold text-slate-900 truncate">
                            {{ selectedFund?.schemeName || selectedFund?.scheme_name }}
                        </div>
                    </div>
                </div>

                <div class="space-y-5">
                    <div class="grid grid-cols-2 gap-5">
                        <div class="form-group">
                            <label class="field-label">Type</label>
                            <select v-model="transactionForm.type" class="premium-input">
                                <option value="BUY">Buy</option>
                                <option value="SELL">Sell</option>
                                <option value="SIP">SIP</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="field-label">Date</label>
                            <input type="date" v-model="transactionForm.date" class="premium-input" />
                        </div>
                    </div>
                    
                    <div class="grid grid-cols-2 gap-5">
                        <div class="form-group">
                            <label class="field-label">Amount (₹)</label>
                            <input type="number" v-model="transactionForm.amount" class="premium-input" placeholder="0.00" />
                        </div>
                        <div class="form-group">
                            <label class="field-label">
                                NAV
                                <span v-if="isNavLoading" class="ml-2 inline-flex items-center text-[10px] text-indigo-500 font-bold uppercase tracking-wider">
                                    <RefreshCw :size="10" class="spin mr-1" /> Fetching...
                                </span>
                            </label>
                            <input type="number" step="0.0001" v-model="transactionForm.nav" class="premium-input" placeholder="0.0000" />
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label class="field-label">Units</label>
                        <input type="number" step="0.001" v-model="transactionForm.units" class="premium-input" placeholder="0.000" />
                    </div>
                </div>

                <div class="modal-footer">
                    <button class="btn btn-text" @click="showTransactionModal = false">Cancel</button>
                    <button class="btn-primary-large" @click="submitTransaction">Confirm</button>
                </div>
            </div>
        </div>

        <!-- IMPORT SUMMARY MODAL -->
        <div v-if="showImportSummary" class="modal-overlay" @click.self="!isPdfImporting && !isEmailImporting ? showImportSummary = false : null">
            <div class="modal-content modal-lg">
                <div class="modal-header">
                    <h2>{{ importStats ? 'Import Summary' : 'Importing...' }}</h2>
                    <button class="close-btn" @click="showImportSummary = false">✕</button>
                </div>
                
                <div class="import-summary-content">
                    <!-- LOADING STATE -->
                    <div v-if="!importStats" class="search-loading-state py-12">
                         <div class="loader-glass-mini">
                            <RefreshCw :size="32" class="spin text-indigo-600 mb-4" />
                            <p class="font-bold text-slate-700">Processing Statement...</p>
                            <p class="text-xs text-slate-500 mt-1">Parsing PDF and mapping funds</p>
                        </div>
                    </div>

                    <!-- RESULTS STATE -->
                    <div v-else>
                        <div class="summary-stats-row">
                            <div class="summary-stat-box success">
                                <span class="stat-count">{{ importStats.processed }}</span>
                                <span class="stat-label">Imported Successfully</span>
                            </div>
                        <div class="summary-stat-box" :class="importStats.details?.failed?.length ? 'failed' : 'neutral'">
                            <span class="stat-count">{{ importStats.details?.failed?.length || 0 }}</span>
                            <span class="stat-label">Skipped</span>
                        </div>
                        <div class="summary-stat-box neutral">
                            <span class="stat-count">{{ importStats.total_found }}</span>
                            <span class="stat-label">Found</span>
                        </div>
                    </div>

                    <div v-if="importStats.details?.failed?.length" class="failed-transactions-list custom-scrollbar mb-4">
                        <h4 class="text-rose-600 font-bold mb-3 text-sm">Failed / Unmapped Transactions</h4>
                        <div v-for="(txn, idx) in importStats.details.failed" :key="idx" class="failed-txn-item">
                            <div class="txn-row-top">
                                <span class="txn-scheme">{{ txn.scheme_name }}</span>
                                <span class="txn-amount text-rose-600">₹{{ txn.amount }}</span>
                            </div>
                            <div class="txn-row-bot">
                                <span class="txn-error">{{ txn.error }}</span>
                                <span class="txn-date">{{ new Date(txn.date).toLocaleDateString() }}</span>
                            </div>
                        </div>
                    </div>

                    <div v-if="importStats.details?.imported?.length" class="failed-transactions-list custom-scrollbar success-border">
                         <h4 class="text-emerald-600 font-bold mb-3 text-sm">Successfully Imported</h4>
                         <div v-for="(txn, idx) in importStats.details.imported" :key="'imp'+idx" class="failed-txn-item">
                            <div class="txn-row-top">
                                <span class="txn-scheme truncate pr-4">{{ txn.mapped_name || txn.scheme_name }}</span>
                                <span class="txn-amount text-emerald-600">{{ txn.type === 'BUY' ? '+' : '-' }}₹{{ txn.amount }}</span>
                            </div>
                            <div class="txn-row-bot">
                                <span class="txn-error text-slate-500">{{ txn.type }} • {{ txn.units }} Units</span>
                                <span class="txn-date">{{ new Date(txn.date).toLocaleDateString() }}</span>
                            </div>
                         </div>
                    </div>
                    
                    <div v-if="!importStats.details?.failed?.length && !importStats.details?.imported?.length" class="success-message-box">
                        <div class="success-icon">🎉</div>
                        <h3>All transactions imported successfully!</h3>
                        <p>Your portfolio has been updated.</p>
                    </div>

                    <div class="action-footer mt-6">
                        <button class="btn-primary-large w-full" @click="showImportSummary = false">
                            Back to Dashboard
                        </button>
                </div>
            </div>
        </div>
    </div>
</div>

        <!-- DELETE CONFIRMATION MODAL - CLEAN MODERN DESIGN -->
        <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="showDeleteConfirm = false">
            <div class="delete-modal-modern">
                <!-- Icon Circle -->
                <div class="delete-icon-wrapper">
                    <Trash2 :size="28" stroke-width="2" />
                </div>
                
                <!-- Content -->
                <div class="delete-modal-content">
                    <h3 class="delete-modal-title">Remove this holding?</h3>
                    <p class="delete-modal-subtitle">This action cannot be undone</p>
                    
                    <!-- Fund Preview -->
                    <div v-if="holdingToDelete" class="delete-fund-preview">
                        <div class="fund-preview-avatar"
                             :style="{ background: getRandomColor(holdingToDelete.scheme_name) }">
                            {{ holdingToDelete.scheme_name[0] }}
                        </div>
                        <div class="fund-preview-details">
                            <div class="fund-preview-name">{{ holdingToDelete.scheme_name }}</div>
                            <div class="fund-preview-meta">
                                <span>{{ holdingToDelete.folio_number || 'No Folio' }}</span>
                                <span class="fund-preview-divider">•</span>
                                <span class="fund-preview-value">{{ formatAmount(holdingToDelete.current_value) }}</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="delete-modal-actions">
                    <button class="delete-btn-cancel" @click="showDeleteConfirm = false">
                        Keep Holding
                    </button>
                    <button class="delete-btn-confirm" @click="proceedDelete">
                        <Trash2 :size="16" />
                        <span>Delete Permanently</span>
                    </button>
                </div>
            </div>
        </div>

    </MainLayout>
</template>

<style scoped>
/* Base Layout */
.content-container {
    width: 100%;
}

.analytics-layout {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.header-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

/* Page Header - Consistent with Insights/Transactions */
.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #e5e7eb;
}

.header-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.page-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: #111827;
    margin: 0;
}

.header-tabs {
    display: flex;
    gap: 0.25rem;
    background: #f3f4f6;
    padding: 0.25rem;
    border-radius: 0.5rem;
    margin: 0 1rem;
}

.tab-btn {
    padding: 0.4rem 1rem;
    border: none;
    background: transparent;
    border-radius: 0.375rem;
    font-size: 0.8125rem;
    font-weight: 600;
    color: #6b7280;
    cursor: pointer;
    transition: all 0.2s;
}

.tab-btn.active {
    background: white;
    color: #4f46e5;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
}

/* Premium AI Card - Midnight Theme */
.ai-card {
    background: #0f172a;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: white;
    padding: 1.75rem 2.25rem;
    border-radius: 1.5rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.ai-card-content {
    position: relative;
    z-index: 10;
}

.ai-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
}

.ai-title-left {
    display: flex;
    align-items: center;
    gap: 1.25rem;
}

.ai-sparkle-icon {
    font-size: 2rem;
    background: rgba(255, 255, 255, 0.1);
    width: 3.5rem;
    height: 3.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 1rem;
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.text-content {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.ai-card-title {
    font-size: 1.125rem;
    font-weight: 800;
    margin: 0;
    letter-spacing: -0.01em;
    color: #f8fafc;
}

.ai-card-subtitle {
    font-size: 0.8125rem;
    color: #94a3b8;
    margin: 4px 0 0 0;
    font-weight: 400;
}

.ai-insight-box {
    background: rgba(15, 23, 42, 0.4);
    padding: 1.5rem;
    border-radius: 1.25rem;
    backdrop-filter: blur(8px);
    margin-bottom: 0.5rem;
    border: 1px solid rgba(255, 255, 255, 0.08);
    max-height: 400px;
    overflow-y: auto;
}

.ai-btn-glass {
    background: rgba(255, 255, 255, 0.05);
    color: white;
    padding: 0.625rem 1.25rem;
    border-radius: 0.75rem;
    font-weight: 600;
    font-size: 0.8125rem;
    border: 1px solid rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    gap: 0.625rem;
    white-space: nowrap;
}

.ai-btn-glass:hover {
    background: rgba(255, 255, 255, 0.15);
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
}

.mesh-blob {
    position: absolute;
    filter: blur(80px);
    opacity: 0.15;
    border-radius: 50%;
    z-index: 1;
}

.blob-1 { width: 400px; height: 400px; background: #3b82f6; top: -150px; right: -100px; }
.blob-2 { width: 350px; height: 350px; background: #6366f1; bottom: -100px; left: -100px; }
.blob-3 { width: 250px; height: 250px; background: #1e40af; top: 10%; left: 20%; }

/* Summary Cards */
.summary-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 2rem;
}

.summary-card {
    background: white;
    padding: 1.5rem;
    border-radius: 1rem;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    display: flex;
    align-items: center;
    gap: 1.25rem;
    transition: all 0.3s ease;
}

.summary-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

.card-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 3rem;
    height: 3rem;
    border-radius: 0.75rem;
    font-size: 1.5rem;
}

.income .card-icon { background: #ecfdf5; color: #10b981; }
.invested .card-icon { background: #e0e7ff; color: #4f46e5; }
.net .card-icon { background: #eff6ff; color: #3b82f6; }

.card-content {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.card-label {
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.card-value {
    display: block;
    font-size: 1.5rem;
    font-weight: 700;
    color: #111827;
}

.card-trend {
    font-size: 0.625rem;
    font-weight: 700;
    margin-top: 0.25rem;
    display: block;
}

/* Filter Bar & Header Alignment */
.filter-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
    background: transparent;
    padding: 0;
    border: none;
}

.filter-left-section {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.transaction-count {
    font-size: 0.875rem;
    color: #64748b;
    font-weight: 600;
    background: #f1f5f9;
    padding: 0.375rem 0.75rem;
    border-radius: 2rem;
}

/* Search Tab - Premium Redesign */
.search-container-premium {
    max-width: 800px;
    margin: 4rem auto;
    display: flex;
    flex-direction: column;
    gap: 3rem;
}

.search-hero {
    position: relative;
    width: 100%;
}

/* Search Tab Redesign */
.search-tab-wrapper {
    width: 100%;
}

.search-hero-section {
    position: relative;
    background: #0f172a;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 2.5rem;
    padding: 5rem 2rem;
    text-align: center;
    overflow: hidden;
    margin-bottom: 3rem;
    box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.2);
}

.search-hero-content {
    position: relative;
    z-index: 10;
    max-width: 700px;
    margin: 0 auto;
}

.hero-tag {
    display: inline-block;
    padding: 0.5rem 1.25rem;
    background: rgba(99, 102, 241, 0.1);
    color: #818cf8;
    border-radius: 100px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1.5rem;
    border: 1px solid rgba(99, 102, 241, 0.2);
}

.hero-title {
    font-size: 3rem;
    font-weight: 800;
    color: white;
    margin-bottom: 1rem;
    letter-spacing: -0.02em;
}

.hero-subtitle {
    font-size: 1.125rem;
    color: #94a3b8;
    margin-bottom: 3rem;
}

.search-main-wrapper {
    position: relative;
    background: white;
    padding: 0.5rem;
    border-radius: 1.25rem;
    display: flex;
    align-items: center;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
}

.search-icon-hero {
    position: absolute;
    left: 1.5rem;
    color: #94a3b8;
}

.search-input-hero {
    width: 100%;
    padding: 1rem 1rem 1rem 3.5rem;
    font-size: 1.125rem;
    border: none;
    outline: none;
    color: #0f172a;
    background: transparent;
}

.search-actions-hero {
    padding-left: 0.5rem;
}

.btn-hero-primary {
    background: #4f46e5;
    color: white;
    padding: 0.875rem 2rem;
    border-radius: 0.875rem;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
}

.btn-hero-primary:hover {
    background: #4338ca;
    transform: translateY(-1px);
}

.hero-mesh {
    position: absolute;
    width: 500px;
    height: 500px;
    filter: blur(100px);
    opacity: 0.3;
    z-index: 1;
}

.mesh-indigo {
    top: -200px;
    right: -100px;
    background: #4f46e5;
}

.mesh-emerald {
    bottom: -200px;
    left: -100px;
    background: #10b981;
}

/* Glass Fund Cards */
.search-results-grid-premium {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 1.5rem;
    padding-bottom: 4rem;
}

.fund-glass-card {
    background: white;
    border: 1px solid #f1f5f9;
    padding: 1.75rem;
    border-radius: 1.75rem;
    cursor: pointer;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    animation: slideUpFade 0.5s ease-out backwards;
}

.fund-glass-card:hover {
    transform: translateY(-8px);
    box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.08);
    border-color: #e2e8f0;
}

.fund-icon-box {
    width: 3.5rem;
    height: 3.5rem;
    border-radius: 1.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 800;
    font-size: 1.25rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
}

.fund-card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}

.fund-meta-badges {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
}

.amfi-badge {
    padding: 0.25rem 0.625rem;
    background: #f1f5f9;
    color: #64748b;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 700;
}

.category-badge {
    padding: 0.25rem 0.625rem;
    background: #fffbeb;
    color: #b45309;
    border-radius: 6px;
    font-size: 0.7rem;
    font-weight: 700;
}

.fund-card-body h3 {
    font-size: 1.125rem;
    font-weight: 700;
    color: #1e293b;
    line-height: 1.4;
    margin-bottom: 1.5rem;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    line-clamp: 2; /* Standard property for compatibility */
}

.fund-card-footer {
    padding-top: 1.25rem;
    border-top: 1px solid #f1f5f9;
}

.fund-action-indicator {
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: #6366f1;
    font-size: 0.8125rem;
    font-weight: 700;
    opacity: 0.6;
    transition: opacity 0.2s;
}

.fund-glass-card:hover .fund-action-indicator {
    opacity: 1;
}

/* Search Loading State */
.search-loading-state {
    padding: 8rem 2rem;
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;
}

.loader-glass {
    background: rgba(255, 255, 255, 0.7);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.3);
    padding: 3rem 4rem;
    border-radius: 2rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.05);
    color: #4f46e5;
}

.loader-glass p {
    font-weight: 700;
    color: #1e293b;
    margin: 0;
}

/* Empty States */
.empty-state-search, .search-onboarding {
    text-align: center;
    padding: 6rem 2rem;
    width: 100%;
}

.empty-glass-icon {
    font-size: 4rem;
    margin-bottom: 2rem;
    opacity: 0.5;
}

.empty-state-search h2 {
    font-size: 1.5rem;
    color: #1e293b;
    margin-bottom: 1rem;
}

.empty-state-search p {
    color: #64748b;
}

.onboarding-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 2rem;
    margin-top: 2rem;
}

.onboarding-item {
    text-align: center;
}

.onboarding-icon {
    font-size: 2.5rem;
    margin-bottom: 1rem;
}

.onboarding-item h4 {
    font-size: 0.9375rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 0.5rem;
}

.onboarding-item p {
    font-size: 0.8125rem;
    color: #64748b;
}

/* Consolidated Search & Filter Bar */
.search-tab-wrapper.full-width {
    width: 100%;
}

.search-filters-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 2rem;
    background: white;
    padding: 0.75rem 1.5rem;
    border-radius: 1rem;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    margin-bottom: 2rem;
}

.filters-scroll-area {
    display: flex;
    gap: 0.75rem;
    overflow-x: auto;
    scrollbar-width: none;
    flex-grow: 1;
}

.filters-scroll-area::-webkit-scrollbar {
    display: none;
}

.filter-search-input-wrapper {
    display: flex;
    align-items: center;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 0.25rem 0.5rem 0.25rem 1rem;
    width: 360px;
    transition: all 0.2s;
}

.filter-search-input-wrapper:focus-within {
    background: white;
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.filter-search-icon {
    color: #94a3b8;
    margin-right: 0.75rem;
}

.filter-search-input {
    border: none;
    outline: none;
    background: transparent;
    font-size: 0.875rem;
    color: #1e293b;
    width: 100%;
    padding: 0.5rem 0;
}

.filter-search-btn {
    background: #0f172a;
    color: white;
    border: none;
    padding: 0.5rem 1.25rem;
    border-radius: 8px;
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
    margin-left: 0.5rem;
}

.filter-search-btn:hover {
    background: #1e293b;
    transform: translateY(-1px);
}

/* Filter Chip Styles */

.filter-chip {
    padding: 0.5rem 1.25rem;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 100px;
    font-size: 0.75rem;
    font-weight: 700;
    color: #64748b;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
}

.filter-chip:hover {
    border-color: #cbd5e1;
    color: #1e293b;
}

.filter-chip.active {
    background: #0f172a;
    border-color: #0f172a;
    color: white;
}

/* Collections section */
.collections-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 1.5rem;
}

.collection-card {
    background: white;
    border: 1px solid #f1f5f9;
    padding: 2rem 1.5rem;
    border-radius: 1.5rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s;
}

.collection-card:hover {
    transform: translateY(-4px);
    border-color: var(--col-color);
    box-shadow: 0 12px 20px -5px rgba(0, 0, 0, 0.05);
}

.col-icon {
    font-size: 2rem;
    margin-bottom: 1rem;
}

.col-name {
    font-size: 0.8125rem;
    font-weight: 800;
    color: #1e293b;
}

/* Card Stats Row */
.fund-stats-row {
    display: flex;
    justify-content: space-between;
    padding: 1rem 0;
    border-top: 1px dashed #e2e8f0;
}

.stat-item label {
    display: block;
    font-size: 0.65rem;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}

.stat-item span {
    font-size: 0.875rem;
}

/* New Badges */
.direct-badge {
    padding: 0.2rem 0.5rem;
    background: #f0fdf4;
    color: #16a34a;
    border-radius: 4px;
    font-size: 0.6rem;
    font-weight: 800;
    text-transform: uppercase;
}

.cat-label {
    font-size: 0.7rem;
    color: #64748b;
    background: #f8fafc;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-weight: 600;
}

.return-label {
    font-size: 0.7rem;
}

/* Discovery Mode Styles */
.search-discovery-section {
    padding-top: 1rem;
    width: 100%;
}

.discovery-header {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    margin-bottom: 2rem;
    margin-top: 2rem;
}

.discovery-header span {
    font-size: 0.75rem;
    font-weight: 800;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    white-space: nowrap;
}

.header-line {
    height: 1px;
    background: #e2e8f0;
    flex-grow: 1;
}

.category-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    justify-content: flex-start;
}

.category-pill {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.75rem 1.25rem;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 100px;
    color: #475569;
    font-weight: 600;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.category-pill:hover {
    border-color: #6366f1;
    color: #6366f1;
    background: #f5f3ff;
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.1);
}

.cat-icon {
    font-size: 1rem;
}

.trending-funds-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
    gap: 1rem;
}

.trending-fund-item {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    background: white;
    border: 1px solid #f1f5f9;
    border-radius: 1.25rem;
    cursor: pointer;
    transition: all 0.3s;
}

.trending-fund-item:hover {
    transform: translateX(4px);
    border-color: #e2e8f0;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
}

.trending-fund-icon {
    width: 2.75rem;
    height: 2.75rem;
    border-radius: 0.875rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 800;
    font-size: 1rem;
    flex-shrink: 0;
}

.trending-fund-info {
    flex-grow: 1;
    min-width: 0;
}

.trending-fund-info h4 {
    font-size: 0.8125rem;
    font-weight: 700;
    color: #1e293b;
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.trending-fund-info span {
    font-size: 0.7rem;
    color: #94a3b8;
    font-weight: 600;
}

.trending-fund-action {
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    background: #f8fafc;
    color: #64748b;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.trending-fund-item:hover .trending-fund-action {
    background: #4f46e5;
    color: white;
    transform: scale(1.1);
}

.amc-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    justify-content: flex-start;
}

.amc-chip {
    padding: 0.5rem 1.25rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    font-size: 0.75rem;
    font-weight: 700;
    color: #64748b;
    cursor: pointer;
    transition: all 0.2s;
}

.amc-chip:hover {
    background: white;
    border-color: #cbd5e1;
    color: #1e293b;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

@keyframes slideUpFade {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

.fund-card {
    background: white;
    padding: 1.5rem;
    border-radius: 1.25rem;
    border: 1px solid #f1f5f9;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02);
}

.fund-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    border-color: #e2e8f0;
}

.fund-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1rem;
}

.fund-info h3 {
    font-size: 1rem;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.4;
    margin: 0 0 0.5rem 0;
}

.fund-category {
    font-size: 0.75rem;
    color: #64748b;
    background: #f8fafc;
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    display: inline-block;
    font-weight: 500;
}

.add-btn-round {
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 50%;
    background: #f1f5f9;
    color: #4f46e5;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    cursor: pointer;
    transition: all 0.2s;
}

.add-btn-round:hover {
    background: #4f46e5;
    color: white;
    transform: scale(1.1);
}


.upload-zone-premium {
    margin: 2rem 0;
    border: 2px dashed #e2e8f0;
    border-radius: 1.5rem;
    padding: 3.5rem 2rem;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    background: #fdfdfd;
    cursor: pointer;
    position: relative;
    overflow: hidden;
}

.upload-zone-premium:hover {
    border-color: #4f46e5;
    background: #f5f3ff;
}

.upload-zone-premium.has-file {
    border-color: #10b981;
    background: #f0fdf4;
    border-style: solid;
}

.upload-icon-circle {
    width: 4.5rem;
    height: 4.5rem;
    background: #f1f5f9;
    color: #64748b;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1.5rem auto;
    transition: all 0.3s;
}

.upload-zone-premium:hover .upload-icon-circle {
    background: #4f46e5;
    color: white;
    transform: scale(1.1);
}

.upload-file-info {
    position: relative;
    z-index: 2;
}

.file-icon-wrapper {
    position: relative;
    display: inline-block;
    color: #10b981;
}

.file-check {
    position: absolute;
    bottom: -2px;
    right: -2px;
    background: #10b981;
    color: white;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    font-size: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid white;
}

.upload-mesh {
    position: absolute;
    width: 200px;
    height: 200px;
    filter: blur(60px);
    opacity: 0.05;
    z-index: 1;
}

.upload-mesh.mesh-1 { top: -50px; left: -50px; background: #4f46e5; }
.upload-mesh.mesh-2 { bottom: -50px; right: -50px; background: #10b981; }

.password-field-group {
    text-align: left;
    margin-top: 2rem;
}


/* Premium Table */
/* Premium Table */
.modern-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: auto;
}

.modern-table th {
    background: #f8fafc;
    padding: 1rem 1.5rem;
    font-size: 0.65rem;
    font-weight: 700;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid #f1f5f9;
}

.modern-table td {
    padding: 0.75rem 1.5rem;
    border-bottom: 1px solid #f8fafc;
    color: #4b5563;
    font-size: 0.875rem;
    vertical-align: middle;
}

.modern-table tr:hover td {
    background: #f9fafb;
}

.modern-table td .font-medium {
    color: #111827;
}

.modern-table .icon-btn {
    width: 32px;
    height: 32px;
    padding: 6px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    border: 1px solid #e5e7eb;
    background: white;
    color: #6b7280;
    transition: all 0.2s;
    margin-left: 0.25rem;
}

.modern-table .icon-btn:hover {
    color: #4f46e5;
    background: #f5f3ff;
    border-color: #c4b5fd;
    transform: translateY(-1px);
}

/* Empty State */
.empty-state-premium {
    padding: 6rem 2rem;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.5rem;
}

.empty-icon-premium {
    font-size: 4rem;
    color: #e2e8f0;
    opacity: 0.8;
}

.empty-text {
    font-size: 1.125rem;
    color: #94a3b8; /* Muted gray */
    font-weight: 500;
}

/* --- UNIFIED IMPORT STYLES (PREMIUM) --- */

/* Side-by-Side Import Grid */
.import-tab-content {
    width: 100%;
}

.import-grid-premium {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 2.5rem;
    margin-top: 1rem;
}

.glass-import-card {
    background: rgba(255, 255, 255, 0.7);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.5);
    border-radius: 2.5rem;
    padding: 3rem;
    box-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.05);
    display: flex;
    flex-direction: column;
    min-height: 600px;
    transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
    overflow: hidden;
}



.adaptive-card {
    min-height: 500px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    transition: all 0.5s ease;
}

.mode-content {
    animation: fadeIn 0.4s ease-out;
    width: 100%;
}

.icon-box-premium {
    width: 3.5rem;
    height: 3.5rem;
    border-radius: 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1.5rem auto;
}

.icon-box-premium.indigo {
    background: #eef2ff;
    color: #4f46e5;
}

.icon-box-premium.emerald {
    background: #ecfdf5;
    color: #059669;
}

.mode-header {
    text-align: center;
    margin-bottom: 2rem;
}

.mode-header h2 {
    font-size: 1.5rem;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 0.5rem;
}

.mode-header p {
    color: #64748b;
}

.info-box-premium {
    background: rgba(239, 246, 255, 0.6);
    border: 1px solid rgba(191, 219, 254, 0.5);
    border-radius: 1rem;
    padding: 1.25rem;
    margin-bottom: 2rem;
    font-size: 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 480px;
    margin-left: auto;
    margin-right: auto;
}

.info-box-premium h4 {
    font-weight: 700;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: flex;
    align-items: center;
}

.field-label {
    display: block;
    font-size: 0.75rem;
    font-weight: 700;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
}

.field-icon {
    position: absolute;
    left: 1rem;
    top: 50%;
    transform: translateY(-50%);
    color: #94a3b8;
}

.field-hint {
    font-size: 0.75rem;
    color: #94a3b8;
    text-align: center;
    margin-top: 0.5rem;
}

.premium-input {
    width: 100%;
    padding: 0.875rem 1rem;
    border-radius: 0.75rem;
    border: 1px solid #e2e8f0;
    background: #fff;
    font-size: 0.95rem;
    transition: all 0.2s;
}

.premium-input:focus {
    outline: none;
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

/* New Integrated Input Group */
.premium-input-group {
    position: relative;
    display: flex;
    align-items: center;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    padding: 0 0.5rem 0 1rem;
    transition: all 0.2s;
    width: 100%;
    min-height: 3.25rem;
}

.premium-input-group:focus-within {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.clean-input {
    flex: 1;
    background: transparent;
    border: none;
    padding: 0.875rem 0.5rem;
    font-size: 0.95rem;
    color: #1e293b;
    width: 100%;
    outline: none;
}

.input-icon-leading {
    color: #94a3b8;
    flex-shrink: 0;
}

.password-toggle-btn {
    width: 2.25rem;
    height: 2.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 0.5rem;
    color: #94a3b8;
    transition: all 0.2s;
    background: transparent;
    border: none;
    cursor: pointer;
    flex-shrink: 0;
}

.password-toggle-btn:hover {
    background: #f1f5f9;
    color: #6366f1;
}

.action-footer {
    margin-top: 2.5rem;
    display: flex;
    justify-content: center;
}

.btn-primary-large {
    background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
    color: white;
    padding: 0.875rem 2.5rem;
    border-radius: 99px;
    font-weight: 600;
    font-size: 1rem;
    box-shadow: 0 10px 20px -5px rgba(79, 70, 229, 0.3);
    transition: all 0.3s;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
}

.btn-primary-large:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 15px 25px -5px rgba(79, 70, 229, 0.4);
}

.btn-premium-primary {
    background: #0f172a;
    color: white;
    border: none;
    padding: 0.625rem 1.25rem;
    border-radius: 0.75rem;
    font-size: 0.8125rem;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    position: relative;
    overflow: hidden;
    transition: all 0.3s;
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.2);
}

.btn-premium-primary:hover {
    transform: translateY(-2px);
    background: #1e293b;
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.3);
}

.btn-premium-secondary {
    background: white;
    color: #475569;
    border: 1px solid #e2e8f0;
    padding: 0.625rem 1.25rem;
    border-radius: 0.75rem;
    font-size: 0.8125rem;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    transition: all 0.3s;
}

.btn-premium-secondary:hover:not(:disabled) {
    background: #f8fafc;
    border-color: #cbd5e1;
    color: #1e293b;
    transform: translateY(-1px);
}

.btn-glow {
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
    opacity: 0;
    transition: opacity 0.3s;
    pointer-events: none;
}

.btn-premium-primary:hover .btn-glow {
    opacity: 1;
}

.info-box-premium.emerald {
    background: rgba(236, 253, 245, 0.6);
    border-color: rgba(167, 243, 208, 0.5);
    color: #064e3b;
}

.btn-primary-large:disabled {
    opacity: 0.7;
    cursor: not-allowed;
    transform: none;
}

.btn-primary-large.emerald-theme {
    background: linear-gradient(135deg, #059669 0%, #047857 100%);
    box-shadow: 0 10px 20px -5px rgba(5, 150, 105, 0.3);
}

.btn-primary-large.emerald-theme:hover:not(:disabled) {
    box-shadow: 0 15px 25px -5px rgba(5, 150, 105, 0.4);
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
/* Modal Styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.3s ease-out;
}

.modal-content {
    background: white;
    width: 100%;
    max-width: 500px;
    border-radius: 2rem;
    padding: 2.5rem;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    position: relative;
    animation: slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.\!p-0 {
    padding: 0 !important;
}

.modal-md {
    max-width: 480px;
}

.modal-lg {
    max-width: 800px;
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
}

.modal-header h2 {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1e293b;
    margin: 0;
}

.close-btn {
    background: #f1f5f9;
    border: none;
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: #64748b;
    transition: all 0.2s;
}

.close-btn:hover {
    background: #e2e8f0;
    color: #0f172a;
}

.modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    margin-top: 2.5rem;
}

@keyframes slideUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
/* Pagination & Sorting Styles */
.load-more-container {
    display: flex;
    justify-content: center;
    padding: 2rem 0;
    width: 100%;
    margin-top: 1rem;
    grid-column: 1 / -1;
}

.load-more-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 2rem;
    font-weight: 600;
    color: #475569;
    cursor: pointer;
    transition: all 0.2s;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.load-more-btn:hover:not(:disabled) {
    border-color: #6366f1;
    color: #6366f1;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}

.load-more-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
}

.sort-dropdown-container {
    position: relative;
    display: flex;
    align-items: center;
    margin-right: 0.5rem;
}

.sort-select {
    appearance: none;
    -webkit-appearance: none;
    background: white;
    border: 1px solid #e2e8f0;
    padding: 0.5rem 2rem 0.5rem 1rem;
    font-size: 0.85rem;
    font-weight: 500;
    color: #475569;
    cursor: pointer;
    outline: none;
    border-radius: 2rem;
    transition: all 0.2s;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    font-size: 0.8rem;
    font-weight: 600;
    color: #475569;
    cursor: pointer;
    outline: none;
    border-radius: 0.5rem;
    transition: background 0.2s;
}

.sort-select:hover {
    border-color: #6366f1;
    color: #6366f1;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}

.sort-select:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
}

.sort-icon {
    position: absolute;
    right: 0.5rem;
    pointer-events: none;
    color: #94a3b8;
}

/* Market Pulse & Premium Discovery */
.market-pulse-hero {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 1.5rem;
    padding: 1.5rem 2rem;
    color: white;
    box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.3);
    position: relative;
    overflow: hidden;
}

.market-pulse-hero::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at center, rgba(99, 102, 241, 0.15) 0%, transparent 50%);
    pointer-events: none;
}

.pulse-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
}

.pulse-header h3 {
    font-size: 1.1rem;
    font-weight: 700;
    margin: 0;
    background: linear-gradient(to right, #fff, #94a3b8);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}

.live-indicator {
    font-size: 0.75rem;
    font-weight: 600;
    color: #10b981;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    background: rgba(16, 185, 129, 0.1);
    padding: 0.2rem 0.6rem;
    border-radius: 1rem;
    border: 1px solid rgba(16, 185, 129, 0.2);
}

.blink {
    animation: blink 1.5s infinite;
}

.indices-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1.5rem;
}

.index-card {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 1rem;
    padding: 1rem;
    backdrop-filter: blur(5px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    transition: transform 0.2s;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.index-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 0.25rem;
}

.index-card:hover {
    transform: translateY(-2px);
    background: rgba(255, 255, 255, 0.08);
}

.index-name {
    font-size: 0.75rem;
    color: #94a3b8;
    font-weight: 600;
    margin-bottom: 0.25rem;
}

.index-val {
    font-size: 1.1rem;
    font-weight: 700;
    color: white;
    margin-bottom: 0.25rem;
}

.index-change {
    font-size: 0.8rem;
    font-weight: 500;
}


.loader-glass-mini {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1.5rem;
    background: white; /* Basic white background since glass is tricky here without bg */
    border: 1px solid #e2e8f0;
    border-radius: 2rem;
    font-size: 0.875rem;
    color: #64748b;
    font-weight: 500;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

/* Premium Trending Funds */
.trending-funds-grid-premium {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
}

.trending-card-premium {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 1.25rem;
    padding: 1.5rem;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    flex-direction: column;
}

.trending-card-premium:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 24px -10px rgba(0, 0, 0, 0.1);
    border-color: #6366f1;
}

.trending-card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1rem;
}

.trending-icon {
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 700;
    font-size: 1rem;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
}

.trend-badge {
    background: #f1f5f9;
    color: #475569;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.trending-card-premium h4 {
    margin: 0 0 1rem 0;
    color: #1e293b;
    font-size: 1rem;
    font-weight: 700;
    line-height: 1.4;
}

/* Import Summary Modal Styles */
.modal-lg {
    max-width: 600px !important;
}

.summary-stats-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 2rem;
}

.summary-stat-box {
    flex: 1;
    background: #f8fafc;
    border-radius: 1rem;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    border: 1px solid #e2e8f0;
}

.summary-stat-box.success {
    background: #ecfdf5;
    border-color: #d1fae5;
    color: #059669;
}

.summary-stat-box.failed {
    background: #fff1f2;
    border-color: #ffe4e6;
    color: #e11d48;
}

.stat-count {
    font-size: 2rem;
    font-weight: 800;
    line-height: 1.2;
}

.stat-label {
    font-size: 0.8rem;
    font-weight: 600;
    opacity: 0.8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.failed-transactions-list {
    max-height: 300px;
    overflow-y: auto;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    padding: 1rem;
}

.failed-txn-item {
    border-bottom: 1px solid #f1f5f9;
    padding: 0.75rem 0;
}

.failed-txn-item:last-child {
    border-bottom: none;
}

.txn-row-top {
    display: flex;
    justify-content: space-between;
    font-weight: 600;
    font-size: 0.9rem;
    margin-bottom: 0.25rem;
}

.txn-row-bot {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: #64748b;
}

.txn-error {
    color: #e11d48;
    font-weight: 500;
}

.success-message-box {
    text-align: center;
    padding: 2rem;
}

.success-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.trending-metrics {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1.25rem;
    padding-bottom: 1.25rem;
    border-bottom: 1px solid #f1f5f9;
}

.trending-metrics .metric {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.trending-metrics .label {
    font-size: 0.75rem;
    color: #94a3b8;
    font-weight: 500;
}

.trending-metrics .value {
    font-size: 0.9rem;
    font-weight: 700;
    color: #334155;
}

.trending-action-btn {
    margin-top: auto;
    width: 100%;
    padding: 0.75rem;
    border-radius: 0.75rem;
    background: #f8fafc;
    color: #475569;
    font-weight: 600;
    font-size: 0.9rem;
    border: none;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
}

.trending-card-premium:hover .trending-action-btn {
    background: #6366f1;
    color: white;
}

/* Modern Delete Modal - Clean & Premium */
.delete-modal-modern {
    background: white;
    width: 90%;
    max-width: 420px;
    border-radius: 1.5rem;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    overflow: hidden;
    animation: modalSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.delete-icon-wrapper {
    width: 64px;
    height: 64px;
    margin: 2.5rem auto 0;
    background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
    border-radius: 1.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #dc2626;
    box-shadow: 0 8px 16px -4px rgba(220, 38, 38, 0.2);
}

.delete-modal-content {
    padding: 1.75rem 2rem 2rem;
    text-align: center;
}

.delete-modal-title {
    font-size: 1.375rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 0.5rem 0;
    letter-spacing: -0.02em;
}

.delete-modal-subtitle {
    font-size: 0.875rem;
    color: #64748b;
    margin: 0 0 1.75rem 0;
}

.delete-fund-preview {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    padding: 1rem;
    display: flex;
    align-items: center;
    gap: 0.875rem;
    text-align: left;
}

.fund-preview-avatar {
    width: 44px;
    height: 44px;
    border-radius: 0.875rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 700;
    font-size: 1rem;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.fund-preview-details {
    flex: 1;
    min-width: 0;
}

.fund-preview-name {
    font-size: 0.9375rem;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 0.375rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.fund-preview-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: #64748b;
}

.fund-preview-divider {
    color: #cbd5e1;
}

.fund-preview-value {
    font-weight: 600;
    color: #10b981;
}

.delete-modal-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    padding: 0 1.5rem 1.5rem;
}

.delete-btn-cancel {
    padding: 0.875rem 1.25rem;
    background: white;
    border: 1.5px solid #e2e8f0;
    border-radius: 0.875rem;
    font-weight: 600;
    font-size: 0.9375rem;
    color: #475569;
    cursor: pointer;
    transition: all 0.2s;
}

.delete-btn-cancel:hover {
    background: #f8fafc;
    border-color: #cbd5e1;
    transform: translateY(-1px);
}

.delete-btn-confirm {
    padding: 0.875rem 1.25rem;
    background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
    border: none;
    border-radius: 0.875rem;
    font-weight: 600;
    font-size: 0.9375rem;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    box-shadow: 0 4px 12px rgba(220, 38, 38, 0.3);
    transition: all 0.2s;
}

.delete-btn-confirm:hover {
    background: linear-gradient(135deg, #b91c1c 0%, #991b1b 100%);
    box-shadow: 0 6px 16px rgba(220, 38, 38, 0.4);
    transform: translateY(-1px);
}

@keyframes modalSlideUp {
    from {
        opacity: 0;
        transform: translateY(20px) scale(0.95);
    }
    to {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
}

.analytics-card {
    background: white;
    border-radius: 1.5rem;
    border: 1px solid #f1f5f9;
    padding: 1.5rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    margin-top: 1.5rem;
}

.analytics-card.full-width {
    width: 100%;
    max-width: 100%;
}

.card-header-flex {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
}

.card-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1e293b;
}

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* Analytics Section Styles */
.analytics-section {
    margin-top: 2rem;
    padding: 1.5rem 0;
}

.section-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 1.5rem;
}

.analytics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
}

.analytics-card {
    background: white;
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    border: 1px solid #e2e8f0;
    transition: all 0.2s;
}

.analytics-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.xirr-card {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.card-icon-large {
    font-size: 2.5rem;
    flex-shrink: 0;
}

.xirr-card .card-content {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.card-label {
    font-size: 0.875rem;
    color: #64748b;
    font-weight: 500;
}

.xirr-value {
    font-size: 2rem;
    font-weight: 700;
}

.xirr-value.positive {
    color: #10b981;
}

.xirr-value.negative {
    color: #ef4444;
}

.card-subtitle {
    font-size: 0.75rem;
    color: #94a3b8;
}

.allocation-card {
    display: flex;
    flex-direction: column;
    align-items: center;
}

.card-header {
    font-size: 1rem;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 1rem;
    width: 100%;
    text-align: center;
}

.performers-card .card-header {
    text-align: left;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.performers-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    width: 100%;
}

.performer-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
    background: #f8fafc;
    border-radius: 8px;
    transition: background 0.2s;
}

.performer-item:hover {
    background: #f1f5f9;
}

.performer-left {
    flex: 1;
    min-width: 0;
}

.performer-name {
    font-size: 0.875rem;
    font-weight: 600;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.performer-code {
    font-size: 0.75rem;
    color: #64748b;
    font-family: monospace;
    margin-top: 0.125rem;
}

.performer-right {
    text-align: right;
    flex-shrink: 0;
    margin-left: 0.75rem;
}

.performer-pl {
    font-size: 0.875rem;
    font-weight: 700;
}

.performer-percent {
    font-size: 0.75rem;
    font-weight: 600;
    opacity: 0.8;
}

.performer-right.positive .performer-pl,
.performer-right.positive .performer-percent {
    color: #10b981;
}

.performer-right.negative .performer-pl,
.performer-right.negative .performer-percent {
    color: #ef4444;
}

.empty-state {
    text-align: center;
    padding: 1.5rem;
    color: #94a3b8;
    font-size: 0.875rem;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

</style>
