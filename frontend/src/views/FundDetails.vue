<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi } from '@/api/client'
import { useNotificationStore } from '@/stores/notification'
import LineChart from '@/components/LineChart.vue'
import { useCurrency } from '@/composables/useCurrency'
import { 
    History,
    Trash2,
    Shield,
    Wallet,
    Edit2,
    ChevronLeft,
    Check,
    Search
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const notify = useNotificationStore()
const { formatAmount } = useCurrency()

const holdingId = route.params.id as string
const holding = ref<any>(null)
const isLoading = ref(true)

async function fetchHoldingDetails() {
    isLoading.value = true
    try {
        let res;
        if (route.query.type === 'aggregate') {
            res = await financeApi.getSchemeDetails(holdingId)
        } else {
            res = await financeApi.getHoldingDetails(holdingId)
        }
        holding.value = res.data
    } catch (e) {
        console.error(e)
        notify.error("Failed to load fund details")
        router.push('/mutual-funds')
    } finally {
        isLoading.value = false
    }
}

onMounted(() => {
    fetchHoldingDetails()
    fetchFamilyMembers()
})

const familyMembers = ref<any[]>([])

async function fetchFamilyMembers() {
    try {
        const res = await financeApi.getUsers()
        familyMembers.value = res.data
    } catch (e) {
        console.error('Failed to fetch family members:', e)
    }
}

const isDropdownOpen = ref(false)
const showUserModal = ref(false)
const searchQuery = ref('')

const filteredUsers = computed(() => {
    if (!searchQuery.value) return familyMembers.value
    
    const query = searchQuery.value.toLowerCase()
    return familyMembers.value.filter(u => 
        u.full_name.toLowerCase().includes(query) || 
        (u.email && u.email.toLowerCase().includes(query))
    )
})

onMounted(() => {
    fetchFamilyMembers()
})

async function updateOwner(userId: string | null) {
    console.log('Updating owner to:', userId)
    
    // Optimistic close or wait? Let's close at end.
    try {
        // Prevent redundant updates
        if (holding.value?.user_id === userId) {
            isDropdownOpen.value = false
            return
        }

        await financeApi.updateHolding(holdingId, { user_id: userId })
        notify.success("Ownership updated successfully")
        
        // Update local holding data to reflect change immediately
        if (holding.value) {
            holding.value.user_id = userId
            
            if (userId) {
                const user = familyMembers.value.find(u => u.id === userId)
                if (user) {
                    holding.value.user_name = user.full_name
                    holding.value.user_avatar = user.avatar
                }
            } else {
                holding.value.user_name = null
                holding.value.user_avatar = null
            }
        }
        // fetchHoldingDetails() // Optional: if we trust the local update, we skip refetch
    } catch (e) {
        console.error('Failed to update ownership:', e)
        notify.error("Failed to update ownership")
    } finally {
        showUserModal.value = false
    }
}

const showDeleteConfirm = ref(false)

async function deleteHolding() {
    try {
        await financeApi.deleteHolding(holdingId)
        notify.success("Holding removed successfully")
        router.push('/mutual-funds')
    } catch (e) {
        notify.error("Failed to delete holding")
    }
}

// Chart Data
const navChartData = computed(() => {
    // Prefer full history if available
    let dataMap = [];
    if (holding.value?.nav_history && holding.value.nav_history.length > 0) {
       dataMap = holding.value.nav_history.map((h: any) => ({
           dateObj: new Date(h.date), // Store object for valid sorting/usage
           date: new Date(h.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' }),
           value: Number(h.value),
           invested: Number(h.value) 
       }));
    } else if (holding.value?.transactions) {
       dataMap = holding.value.transactions.map((t: any) => ({
            dateObj: new Date(t.date),
            date: new Date(t.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' }),
            value: Number(t.nav),
            invested: Number(t.nav)
        }));
    }
    
    // Sort safely using date objects
    return dataMap.sort((a: any, b: any) => a.dateObj.getTime() - b.dateObj.getTime());
});

// Transaction markers for chart
const transactionMarkers = computed(() => {
    if (!holding.value?.transactions) return []
    
    return holding.value.transactions.map((t: any) => ({
        date: new Date(t.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' }),
        type: t.type,
        amount: Number(t.amount),
        units: Number(t.units)
    }))
})

const isImageUrl = (avatar: string) => {
    return avatar && (avatar.startsWith('http') || avatar.startsWith('/'));
}

const formatDate = (dateStr: string) => {
    if (!dateStr) return '-'
    // Ensure we handle YYYY-MM-DD correctly without timezone shifts
    const [year, month, day] = dateStr.split('-').map(Number)
    const date = new Date(year, month - 1, day)
    return date.toLocaleDateString('en-GB', { 
        day: 'numeric', 
        month: 'short', 
        year: 'numeric' 
    })
}
</script>

<template>
    <MainLayout>
        <div class="page-container">
            <div v-if="isLoading" class="flex items-center justify-center min-h-[400px]">
                <div class="loader"></div>
            </div>

            <div v-else-if="holding" class="anim-fade-in">
                <!-- Header -->
                <div class="page-header">
                    <div class="header-left">
                        <button class="back-pill" @click="router.back()">
                            <ChevronLeft :size="20" />
                        </button>
                        <div class="flex flex-col gap-2">
                             <h1 class="page-title mb-1">{{ holding.scheme_name }}</h1>
                             <div class="meta-row">
                                <span class="badge">{{ holding.category || 'Mutual Fund' }}</span>
                                <span class="pill-meta">{{ holding.scheme_code }}</span>
                                <span class="pill-meta">NAV: {{ formatAmount(holding.last_nav) }}</span>
                             </div>
                        </div>
                    </div>
                    
                    <div class="header-actions">
                        <button v-if="!holding.is_aggregate" class="btn-danger" @click="showDeleteConfirm = true">
                            <Trash2 :size="16" />
                            Remove Holding
                        </button>
                    </div>
                </div>

                <div class="main-grid">
                    <!-- Left Column -->
                    <div class="content-column">
                        <!-- Hero Stats + Chart -->
                        <div class="hero-card">
                            <div class="hero-bg-glow"></div>
                            <div class="relative z-10">
                                <div class="hero-header">
                                    <div class="icon-circle">
                                        <Wallet class="text-indigo-400" :size="20" />
                                    </div>
                                    <h2 class="text-lg font-bold text-indigo-100">Performance Overview</h2>
                                </div>

                                <div class="stats-grid mb-8">
                                    <div class="stat-item">
                                        <div class="stat-label">Current Value</div>
                                        <div class="stat-value">{{ formatAmount(holding.current_value) }}</div>
                                        <div class="stat-sub">Invested: {{ formatAmount(holding.invested_value) }}</div>
                                    </div>
                                    
                                    <div class="stat-item">
                                        <div class="stat-label">Total Returns</div>
                                        <div class="stat-value" :class="holding.profit_loss >= 0 ? 'text-emerald-400' : 'text-rose-400'">
                                            {{ holding.profit_loss >= 0 ? '+' : '' }}{{ formatAmount(holding.profit_loss) }}
                                        </div>
                                        <div class="stat-sub">
                                            {{ holding.invested_value > 0 ? ((holding.profit_loss / holding.invested_value) * 100).toFixed(2) : '0.00' }}% Absolute
                                        </div>
                                    </div>

                                    <div class="stat-item">
                                        <div class="stat-label">XIRR</div>
                                        <div class="stat-value text-indigo-300">
                                            {{ holding.xirr ? holding.xirr.toFixed(2) + '%' : 'N/A' }}
                                        </div>
                                        <div class="stat-sub">Annualized Return</div>
                                    </div>
                                </div>
                                
                                <div class="h-48 w-full">
                                    <LineChart 
                                        :data="navChartData" 
                                        :markers="transactionMarkers"
                                        :hide-legend="true"
                                        y-min="auto"
                                        value-label="NAV"
                                        invested-label="NAV"
                                    />
                                </div>
                            </div>
                        </div>

                        <!-- Transactions -->
                        <div class="analytics-card">
                            <div class="card-header">
                                <h3 class="card-title">
                                    <History :size="18" class="text-slate-400" />
                                    Transaction History
                                </h3>
                            </div>
                            <div class="table-wrapper">
                                <table class="standard-table">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Type</th>
                                            <th class="text-right">Units</th>
                                            <th class="text-right">NAV</th>
                                            <th class="text-right">Amount</th>
                                            <th v-if="holding.is_aggregate" class="text-right">Member</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="order in holding.transactions" :key="order.id">
                                            <td class="text-slate-600">{{ formatDate(order.date) }}</td>
                                            <td>
                                                <span 
                                                    class="badge-pill"
                                                    :class="order.type === 'BUY' || order.type === 'SIP' ? 'emerald' : 'rose'"
                                                >
                                                    {{ order.type.toLowerCase() }}
                                                </span>
                                            </td>
                                            <td class="font-mono text-right">{{ order.units.toFixed(3) }}</td>
                                            <td class="font-mono text-right">{{ order.nav.toFixed(2) }}</td>
                                            <td class="font-bold text-right">{{ formatAmount(order.amount) }}</td>
                                            <td v-if="holding.is_aggregate" class="text-right pl-4">
                                                <div class="flex justify-end">
                                                    <div v-if="order.user" class="member-avatar-mini w-6 h-6 text-[10px]" :title="order.user.name">
                                                        {{ order.user.avatar || '👤' }}
                                                    </div>
                                                    <span v-else class="text-xs text-slate-400">-</span>
                                                </div>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- Right Column -->
                    <div class="sidebar-column">
                        <div class="analytics-card">
                            <h4 class="sidebar-title">
                                <Shield :size="14" /> Ownership
                            </h4>
                            
                            <div 
                                class="owner-box premium-owner"
                                :class="{ 'interactive': !holding.is_aggregate }"
                                @click="!holding.is_aggregate && (showUserModal = true)"
                            >
                                <div class="avatar-ring">
                                    <template v-if="(holding.user_avatar || familyMembers.find(u => u.id === holding.user_id)?.avatar) && isImageUrl(holding.user_avatar || familyMembers.find(u => u.id === holding.user_id)?.avatar)">
                                        <img :src="holding.user_avatar || familyMembers.find(u => u.id === holding.user_id)?.avatar" class="avatar-img" />
                                    </template>
                                    <div v-else class="avatar">
                                        {{ holding.user_avatar || familyMembers.find(u => u.id === holding.user_id)?.avatar || '👤' }}
                                    </div>
                                </div>
                                <div class="owner-info flex-1">
                                    <div class="label-xs-caps">Assigned To</div>
                                    <div class="owner-name-lg">
                                        {{ holding.user_name || familyMembers.find(u => u.id === holding.user_id)?.full_name || 'Unassigned' }}
                                    </div>
                                </div>
                                <div v-if="!holding.is_aggregate" class="edit-icon">
                                    <Edit2 :size="18" class="text-slate-400" />
                                </div>
                            </div>
                            
                            <!-- Multiple Owners List -->
                            <div v-if="holding.is_aggregate && holding.owners && holding.owners.length > 1" class="px-6 pb-6">
                                <div class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Includes portfolios of:</div>
                                <div class="flex flex-col gap-2">
                                    <div v-for="owner in holding.owners" :key="owner.id" class="flex items-center gap-2 bg-slate-50 p-2 rounded-lg border border-slate-100">
                                         <div class="w-6 h-6 rounded-full bg-white flex items-center justify-center text-xs border border-slate-200 shadow-sm">
                                            {{ owner.avatar || '👤' }}
                                         </div>
                                         <span class="text-sm font-medium text-slate-700">{{ owner.name }}</span>
                                    </div>
                                </div>
                            </div>

                        </div>






                        <div class="analytics-card">
                            <h4 class="sidebar-title">Fund Details</h4>
                            <div class="details-list">
                                <div class="detail-row">
                                    <span class="label-detail">Folio Number</span>
                                    <span class="value-detail">{{ holding.folio_number || 'N/A' }}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="label-detail">Average Price</span>
                                    <span class="value-detail">{{ formatAmount(holding.average_price) }}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="label-detail">Last Updated</span>
                                    <span class="value-detail">{{ holding.last_updated_at || 'Never' }}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="label-detail">User ID</span>
                                    <span class="value-detail font-mono text-xs">{{ holding.user_id || 'None' }}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- User Selection Modal -->
        <div v-if="showUserModal" class="modal-overlay" @click="showUserModal = false">
            <div class="user-picker-modal" @click.stop>
                <div class="modal-header">
                    <h3 class="modal-title">Assign Owner</h3>
                    <button class="close-btn" @click="showUserModal = false">
                        <span class="text-2xl leading-none">&times;</span>
                    </button>
                </div>
                
                <div class="modal-search">
                    <div class="search-input-wrapper">
                        <Search :size="16" class="search-icon" />
                        <input 
                            v-model="searchQuery" 
                            type="text" 
                            placeholder="Search family members..." 
                            class="search-input"
                            autofocus
                        />
                    </div>
                </div>

                <div class="user-list-scroll">
                    <!-- Self Option (Always visible or filtered? Let's keep distinct) -->
                    <div 
                        class="picker-item" 
                        :class="{ 'selected': !holding.user_id }"
                        @click="updateOwner(null)"
                        v-if="!searchQuery || 'unassigned self'.includes(searchQuery.toLowerCase())"
                    >
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-lg">👤</div>
                            <span class="font-medium text-slate-700">Unassigned (Self)</span>
                        </div>
                        <Check v-if="!holding.user_id" :size="20" class="text-indigo-600" />
                    </div>
                    
                    <div 
                        v-for="user in filteredUsers" 
                        :key="user.id" 
                        class="picker-item"
                        :class="{ 'selected': holding.user_id === user.id }"
                        @click="updateOwner(user.id)"
                    >
                        <div class="flex items-center gap-3">
                            <img v-if="isImageUrl(user.avatar)" :src="user.avatar" class="w-10 h-10 rounded-full object-cover shadow-sm" />
                            <div v-else class="w-10 h-10 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center text-sm font-bold shadow-sm border border-indigo-100">
                                {{ user.avatar || user.full_name[0] }}
                            </div>
                            <div class="flex flex-col">
                                <span class="font-medium text-slate-800">{{ user.full_name }}</span>
                                <span class="text-xs text-slate-400">{{ user.email }}</span>
                            </div>
                        </div>
                        <Check v-if="holding.user_id === user.id" :size="20" class="text-indigo-600" />
                    </div>

                    <!-- Empty State -->
                    <div v-if="filteredUsers.length === 0 && !('unassigned self'.includes(searchQuery.toLowerCase()))" class="empty-search-state">
                        <Search :size="32" class="text-slate-300 mb-2" />
                        <p class="text-slate-500 text-sm">No users found matching "{{ searchQuery }}"</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Delete Modal -->
        <div v-if="showDeleteConfirm" class="modal-overlay">
            <div class="delete-modal-modern">
                <div class="delete-icon-wrapper">
                    <Trash2 :size="28" />
                </div>
                <div class="delete-modal-content">
                    <h3 class="delete-modal-title">Delete Holding?</h3>
                    <p class="delete-modal-subtitle">
                        Are you sure you want to remove <strong>{{ holding?.scheme_name }}</strong>? This will permanently delete all transaction history.
                    </p>
                    <div class="delete-modal-actions">
                        <button class="delete-btn-cancel" @click="showDeleteConfirm = false">Cancel</button>
                        <button class="delete-btn-confirm" @click="deleteHolding">
                            <Trash2 :size="18" /> Delete Forever
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </MainLayout>
</template>

<style scoped>
.page-container {
    max-width: 1600px;
    margin: 0 auto;
    padding: 2rem;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #e2e8f0;
}

@media (max-width: 768px) {
    .page-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 1.5rem;
    }
}

.header-left {
    display: flex;
    align-items: flex-start;
    gap: 1.5rem;
}

.back-pill {
    width: 2.5rem;
    height: 2.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f1f5f9;
    border-radius: 0.5rem;
    color: #475569;
    transition: all 0.2s;
    border: 1px solid #e2e8f0;
}

.back-pill:hover {
    background: #e2e8f0;
    color: #1e293b;
    border-color: #cbd5e1;
}

.page-title {
    font-size: 1.5rem;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.2;
}

.badge {
    background: #eff6ff;
    color: #3b82f6;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 0.25rem 0.625rem;
    border-radius: 999px;
    text-transform: uppercase;
    border: 1px solid #dbeafe;
}

.meta-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.875rem;
    color: #64748b;
    flex-wrap: wrap;
}

.pill-meta {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    color: #475569;
}

.btn-danger {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.625rem 1.25rem;
    background: #fff1f2;
    border: 1px solid #fecdd3;
    border-radius: 0.75rem;
    font-weight: 600;
    color: #e11d48;
    transition: all 0.2s;
    font-size: 0.875rem;
}

.btn-danger:hover {
    background: #ffe4e6;
    border-color: #fda4af;
    transform: translateY(-1px);
}

.main-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 2rem;
}

@media (min-width: 1024px) {
    .main-grid {
        grid-template-columns: 2fr 1fr;
    }
}

.content-column {
    display: flex;
    flex-direction: column;
    gap: 2rem;
}

/* Hero Card - Midnight Theme */
.hero-card {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    border-radius: 1.5rem;
    padding: 2.5rem;
    color: white;
    box-shadow: 0 20px 25px -5px rgba(15, 23, 42, 0.3);
    position: relative;
    overflow: hidden;
}

.hero-bg-glow {
    position: absolute;
    top: -50px;
    right: -50px;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}

.hero-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 2rem;
}

.icon-circle {
    width: 3rem;
    height: 3rem;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 2rem;
}

.stat-label {
    font-size: 0.875rem;
    color: #94a3b8;
    margin-bottom: 0.5rem;
    font-weight: 500;
}

.stat-value {
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: 0.25rem;
    line-height: 1.1;
}

.stat-sub {
    font-size: 0.875rem;
    color: #64748b;
}

/* Analytics Card & Table */
.analytics-card {
    background: white;
    border-radius: 1.5rem;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

.card-header {
    padding: 1.5rem 2rem;
    border-bottom: 1px solid #f1f5f9;
}

.card-title {
    font-size: 1.125rem;
    font-weight: 700;
    color: #1e293b;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.sidebar-title {
    font-size: 0.875rem;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1.5rem;
    padding: 1.5rem 1.5rem 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.table-wrapper {
    width: 100%;
    overflow-x: auto;
}

.standard-table {
    width: 100%;
    border-collapse: collapse;
}

.standard-table th {
    text-align: left;
    padding: 1rem 2rem;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    color: #64748b;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    white-space: nowrap;
}

.standard-table td {
    padding: 1.25rem 2rem;
    border-bottom: 1px solid #f1f5f9;
    font-size: 0.9375rem;
    white-space: nowrap;
}

.standard-table tr:hover {
    background: #f8fafc;
}

.badge-pill {
    display: inline-flex;
    align-items: center;
    padding: 0.375rem 0.875rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: capitalize;
}

.badge-pill.emerald { background: #dcfce7; color: #15803d; }
.badge-pill.rose { background: #ffe4e6; color: #be123c; }

/* Sidebar Styles */
.sidebar-column {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.owner-box.premium-owner {
    background: linear-gradient(to right, #f8fafc, #f1f5f9);
    border: 1px solid #e2e8f0;
    margin: 0 1.5rem 1.5rem;
    padding: 1.5rem;
    border-radius: 1rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    transition: all 0.2s;
}

.owner-box.premium-owner.interactive {
    cursor: pointer;
}

.owner-box.premium-owner.interactive:hover {
    background: white;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    border-color: #cbd5e1;
}

.owner-box.premium-owner.interactive:hover .edit-icon {
    opacity: 1;
    transform: translateX(0);
}

.edit-icon {
    opacity: 0;
    transform: translateX(-10px);
    transition: all 0.2s;
}

.flex-1 { flex: 1; }

.avatar-ring {
    padding: 3px;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 50%;
}

.avatar {
    width: 3.5rem;
    height: 3.5rem;
    background: #fee2e2; /* Fallback color */
    color: #ef4444;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.avatar-img {
    width: 3.5rem;
    height: 3.5rem;
    border-radius: 50%;
    object-fit: cover;
}

.label-xs-caps { 
    font-size: 0.65rem; 
    color: #64748b; 
    font-weight: 700; 
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.25rem;
}

.owner-name-lg { 
    font-weight: 800; 
    color: #0f172a; 
    font-size: 1.125rem; 
}

.form-group { padding: 0 1.5rem 1.5rem; }
.label-sm { display: block; font-size: 0.8rem; font-weight: 600; color: #64748b; margin-bottom: 0.5rem; }

/* Custom Dropdown Styles */
.premium-select-trigger {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
    z-index: 10;
}

.premium-select-trigger:hover {
    border-color: #cbd5e1;
    background: #f8fafc;
}

.custom-options-container {
    position: absolute;
    top: calc(100% + 0.5rem);
    left: 0;
    right: 0;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    z-index: 100;
    padding: 0.5rem;
    max-height: 240px;
    overflow-y: auto;
    animation: fadeIn 0.1s ease-out;
}

.option-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.625rem 0.75rem;
    border-radius: 0.5rem;
    cursor: pointer;
    transition: all 0.1s;
    color: #1e293b;
}

.option-item:hover {
    background: #f1f5f9;
}

.option-item.selected {
    background: #eff6ff;
    color: #4338ca;
}

.details-list { padding: 0 1.5rem 1.5rem; }
.detail-row {
    display: flex;
    justify-content: space-between;
    padding: 0.875rem 0;
    border-bottom: 1px solid #f1f5f9;
}
.detail-row:last-child { border-bottom: none; padding-bottom: 0; }
.label-detail { font-size: 0.9rem; color: #64748b; }
.value-detail { font-size: 0.9rem; font-weight: 600; color: #1e293b; }

/* Modal Styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(15, 23, 42, 0.7);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
    animation: fadeIn 0.2s ease-out;
}

.delete-modal-modern {
    background: white;
    width: 90%;
    max-width: 440px;
    border-radius: 1.5rem;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    overflow: hidden;
    animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.delete-icon-wrapper {
    width: 72px;
    height: 72px;
    margin: 2.5rem auto 1.5rem;
    background: #fef2f2;
    border-radius: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ef4444;
}

.delete-modal-content {
    padding: 0 2.5rem 2.5rem;
    text-align: center;
}

.delete-modal-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.5rem;
}

.delete-modal-subtitle {
    font-size: 1rem;
    color: #64748b;
    margin-bottom: 2rem;
    line-height: 1.6;
}

.delete-modal-actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

.delete-btn-cancel {
    padding: 0.875rem;
    background: white;
    border: 1px solid #cbd5e1;
    border-radius: 0.75rem;
    font-weight: 600;
    color: #475569;
    cursor: pointer;
    font-size: 1rem;
}

.delete-btn-confirm {
    padding: 0.875rem;
    background: #ef4444;
    border: none;
    border-radius: 0.75rem;
    font-weight: 600;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    font-size: 1rem;
}

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

/* User Picker Modal Styles */
.user-picker-modal {
    background: white;
    width: 90%;
    max-width: 400px;
    border-radius: 1.5rem;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
    overflow: hidden;
    animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    max-height: 80vh;
    display: flex;
    flex-direction: column;
}

.modal-header {
    padding: 1.5rem 1.5rem 1rem;
    border-bottom: none; /* Removed border as search has it */
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.modal-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #0f172a;
}

.close-btn {
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #64748b;
    background: transparent;
    border: none;
    cursor: pointer;
    transition: all 0.2s;
}

.close-btn:hover {
    background: #f1f5f9;
    color: #ef4444;
}


/* Search Styles */
.modal-search {
    padding: 0 1.5rem 1rem;
    border-bottom: 1px solid #f1f5f9;
}

.search-input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
}

.search-icon {
    position: absolute;
    left: 1rem;
    color: #94a3b8;
    pointer-events: none;
}

.search-input {
    width: 100%;
    padding: 0.75rem 1rem 0.75rem 2.75rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    color: #1e293b;
    font-size: 0.95rem;
    outline: none;
    transition: all 0.2s;
}

.search-input:focus {
    background: white;
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.empty-search-state {
    padding: 3rem 1rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
}

/* Scroll adjustment */
.user-list-scroll {
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    /* Reduce height if needed or keep flexible */
}

.picker-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    border-radius: 1rem;
    cursor: pointer;
    transition: all 0.2s;
    border: 1px solid transparent;
}

.picker-item:hover {
    background: #f8fafc;
    border-color: #e2e8f0;
}

.picker-item.selected {
    background: #eff6ff;
    border-color: #dbeafe;
}

@keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.anim-fade-in { animation: fadeIn 0.4s ease-out forwards; }
.loader {
    width: 48px;
    height: 48px;
    border: 3px solid #e2e8f0;
    border-top-color: #6366f1;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
