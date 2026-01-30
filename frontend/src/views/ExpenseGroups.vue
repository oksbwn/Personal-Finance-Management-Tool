<template>
    <MainLayout>
        <div class="expense-groups-view">
            <!-- Compact Header -->
            <div class="page-header">
                <div class="header-left">
                    <h1 class="page-title">Expense Groups</h1>
                    <span class="transaction-count">{{ filteredGroups.length }} groups</span>
                </div>

                <div class="header-actions">
                    <button class="btn-compact btn-primary" @click="openAddModal">
                        <Plus />
                        New Group
                    </button>
                </div>
            </div>

            <!-- Filter Bar (Matches Transactions) -->
            <div class="filter-bar">
                <div class="search-box-compact">
                    <Search class="search-icon" />
                    <input v-model="searchQuery" placeholder="Search groups..." />
                </div>

                <div class="year-filter-wrapper">
                    <CustomSelect v-model="selectedYear" :options="yearOptions" placeholder="Year" class="year-select"
                        style="width: 140px;" />
                </div>
            </div>

            <div v-if="loading" class="loading-state-premium">
                <div class="loader-ring"></div>
                <p>Fetching your expense groups...</p>
            </div>

            <div v-else class="groups-container">
                <div v-if="filteredGroups.length === 0" class="empty-state-premium glass-card">
                    <div class="empty-content">
                        <h2>No Expense Groups found. <span class="link-action" @click="openAddModal">Add One.</span>
                        </h2>
                    </div>
                </div>

                <div v-else class="groups-grid">
                    <div v-for="group in filteredGroups" :key="group.id" class="group-card-modern">

                        <!-- Top Row: Avatar + Title + Actions -->
                        <div class="card-top-row">
                            <div class="group-icon-avat"
                                :style="{ backgroundColor: generateColor(group.name).bg, color: generateColor(group.name).text }">
                                <span v-if="group.icon" style="font-size: 1.5rem;">{{ group.icon }}</span>
                                <span v-else>{{ group.name.charAt(0).toUpperCase() }}</span>
                            </div>
                            <div class="group-header-text">
                                <h3 class="group-title">{{ group.name }}</h3>
                                <div class="group-meta-row">
                                    <span class="status-dot-mini" :class="{ 'on': group.is_active }"></span>
                                    <span class="status-label-mini">{{ group.is_active ? 'Active' : 'Archived' }}</span>
                                </div>
                            </div>
                            <div class="card-actions-float">
                                <button class="action-btn-mini" @click.stop="openEditModal(group)">
                                    <Pencil :size="14" />
                                </button>
                                <button class="action-btn-mini danger" @click.stop="confirmDelete(group)">
                                    <Trash2 :size="14" />
                                </button>
                            </div>
                        </div>

                        <div class="card-body-modern">
                            <p class="card-desc-modern">{{ group.description || 'No description provided.' }}</p>

                            <!-- Budget Box -->
                            <div class="budget-box-modern" v-if="Number(group.budget) > 0">
                                <div class="budget-header-modern">
                                    <span class="budget-label-modern">Budget Usage</span>
                                    <span class="budget-pct-modern" :class="getBudgetColor(group)">{{
                                        getBudgetPercentage(group).toFixed(0) }}%</span>
                                </div>
                                <div class="progress-track-modern">
                                    <div class="progress-fill-modern"
                                        :style="{ width: getBudgetPercentage(group) + '%', backgroundColor: getBudgetColorCode(group) }">
                                    </div>
                                </div>
                                <div class="budget-stats-grid">
                                    <div class="stat-item">
                                        <span class="stat-lbl">Spent</span>
                                        <span class="stat-val">{{ formatAmount(group.total_spend || 0) }}</span>
                                    </div>
                                    <div class="stat-div"></div>
                                    <div class="stat-item">
                                        <span class="stat-lbl">Left</span>
                                        <span class="stat-val"
                                            :class="((group.budget - (group.total_spend || 0)) < 0) ? 'text-red-500' : ''">
                                            {{ formatAmount(group.budget - (group.total_spend || 0)) }}
                                        </span>
                                    </div>
                                </div>
                            </div>
                            <div v-else class="no-budget-badge-modern">
                                <span>No Budget Set</span>
                            </div>
                        </div>

                        <div class="card-footer-modern">
                            <div class="footer-item">
                                <Calendar :size="14" class="text-icon" />
                                <span>
                                    {{ group.start_date ? formatDate(group.start_date) : 'Starts -' }}
                                    {{ group.end_date ? ' - ' + formatDate(group.end_date) : '' }}
                                </span>
                            </div>
                            <div class="footer-item" v-if="!group.budget">
                                <span class="font-bold">{{ formatAmount(group.total_spend || 0) }} spent</span>
                            </div>
                        </div>
                        <!-- End Groups Grid -->
                    </div>
                </div>
                <!-- End Groups Grid -->

                <!-- Add/Edit Modal -->
                <div v-if="showModal" class="modal-overlay-global">
                    <div class="modal-global glass premium-modal animate-in compact-modal">
                        <div class="modal-header-clean">
                            <div class="header-text">
                                <h2 class="modal-title">{{ isEditing ? 'Edit Expense Group' : 'Create Expense Group' }}
                                </h2>
                                <p class="modal-subtitle">Organize your expenses into logical buckets.</p>
                            </div>
                            <button class="btn-icon-circle-subtle" @click="showModal = false">
                                <X :size="20" />
                            </button>
                        </div>

                        <form @submit.prevent="handleSubmit" class="form-premium-clean">

                            <!-- Icon Selection -->
                            <div class="form-group mb-5">
                                <label class="form-label-clean" style="text-align: center;">Group Icon</label>
                                <div class="icon-selector-wrapper">
                                    <div class="icon-preview-large">
                                        {{ form.icon || '?' }}
                                    </div>
                                    <div class="icon-presets">
                                        <button type="button"
                                            v-for="emoji in ['✈️', '🏠', '🍔', '🛒', '💊', '🎓', '🎮', '🎁', '💸', '💼', '🚗', '👶']"
                                            :key="emoji" class="emoji-btn" :class="{ 'selected': form.icon === emoji }"
                                            @click="form.icon = emoji">
                                            {{ emoji }}
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <!-- Name Field -->
                            <div class="form-group mb-5">
                                <label class="form-label-clean">Group Name</label>
                                <div class="input-with-icon">
                                    <Type class="input-icon" :size="18" />
                                    <input v-model="form.name" class="form-input-clean" required
                                        placeholder="e.g. Thailand Trip 2026" autofocus />
                                </div>
                            </div>

                            <!-- Description Field -->
                            <div class="form-group mb-5">
                                <label class="form-label-clean">Description</label>
                                <textarea v-model="form.description" class="form-input-clean textarea" rows="2"
                                    placeholder="Add a short description..."></textarea>
                            </div>

                            <div class="grid-2-col mb-5">
                                <!-- Budget Field -->
                                <div class="form-group">
                                    <label class="form-label-clean">Total Budget</label>
                                    <div class="input-with-icon">
                                        <Wallet class="input-icon" :size="18" />
                                        <input type="number" v-model="form.budget" class="form-input-clean"
                                            placeholder="0.00" />
                                    </div>
                                </div>
                                <!-- Active Toggle -->
                                <div class="form-group toggle-group-clean">
                                    <label class="form-label-clean">Active Status</label>
                                    <div class="toggle-card" :class="{ 'active': form.is_active }"
                                        @click="form.is_active = !form.is_active">
                                        <span class="status-text">{{ form.is_active ? 'Active' : 'Inactive' }}</span>
                                        <div class="toggle-switch-mini" :class="{ 'on': form.is_active }"></div>
                                    </div>
                                </div>
                            </div>

                            <!-- Date Range -->
                            <label class="form-label-clean">Duration (Optional)</label>
                            <div class="date-range-box mb-6">
                                <div class="date-field">
                                    <Calendar class="date-icon" :size="16" />
                                    <input type="date" v-model="form.start_date" class="date-input-clean"
                                        placeholder="Start" />
                                </div>
                                <span class="date-arrow">→</span>
                                <div class="date-field">
                                    <Calendar class="date-icon" :size="16" />
                                    <input type="date" v-model="form.end_date" class="date-input-clean"
                                        placeholder="End" />
                                </div>
                            </div>

                            <div class="modal-footer-clean">
                                <button type="button" @click="showModal = false"
                                    class="btn-clean-secondary">Cancel</button>
                                <button type="submit" class="btn-clean-primary">
                                    {{ isEditing ? 'Save Changes' : 'Create Group' }}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- Delete Confirmation -->
                <div v-if="showDeleteConfirm" class="modal-overlay-global">
                    <div class="modal-global glass premium-modal animate-in compact-modal"
                        style="max-width: 400px; text-align: center; padding: 2rem;">
                        <div class="delete-icon-wrapper mb-4">
                            <Trash2 :size="32" class="text-red-500" />
                        </div>
                        <h2 class="text-xl font-bold text-slate-800 mb-2">Delete Group?</h2>
                        <p class="text-slate-500 mb-6 text-sm leading-relaxed">
                            Are you sure you want to delete <strong class="text-slate-700">{{ groupToDelete?.name
                                }}</strong>?
                            <br>This action cannot be undone.
                        </p>
                        <div class="flex gap-3 justify-center">
                            <button @click="showDeleteConfirm = false" class="btn-clean-secondary">Cancel</button>
                            <button @click="doDelete" class="btn-clean-msg-danger">Delete Group</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </MainLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Plus, Pencil, Trash2, Search, Calendar, Wallet, Type, X } from 'lucide-vue-next'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi } from '@/api/client'
import CustomSelect from '@/components/CustomSelect.vue'
import { useCurrency } from '@/composables/useCurrency'
import { useNotificationStore } from '@/stores/notification'

const notify = useNotificationStore()
const { formatAmount } = useCurrency()
const loading = ref(true)
const expenseGroups = ref<any[]>([])
const searchQuery = ref('')

const showModal = ref(false)
const isEditing = ref(false)
const editingId = ref<string | null>(null)
const form = ref({
    name: '',
    description: '',
    is_active: true,
    budget: 0,
    start_date: '',
    end_date: '',
    icon: ''
})

const selectedYear = ref<string>('All')

const showDeleteConfirm = ref(false)
const groupToDelete = ref<any>(null)

const yearOptions = computed(() => {
    const currentYear = new Date().getFullYear()
    const years = []
    years.push({ label: 'All Years', value: 'All' })

    // Generate years from Next Year down to 2018
    for (let y = currentYear + 1; y >= 2018; y--) {
        years.push({ label: y.toString(), value: y.toString() })
    }
    return years
})

const filteredGroups = computed(() => {
    let result = expenseGroups.value

    // Year Filter
    if (selectedYear.value && selectedYear.value !== 'All') {
        result = result.filter(g => {
            const dateToUse = g.start_date || g.created_at
            if (!dateToUse) return false
            return new Date(dateToUse).getFullYear().toString() === selectedYear.value
        })
    }

    // Search Filter
    if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase()
        result = result.filter(g =>
            g.name.toLowerCase().includes(q) ||
            (g.description && g.description.toLowerCase().includes(q))
        )
    }

    return result
})

const fetchGroups = async () => {
    loading.value = true
    try {
        const res = await financeApi.getExpenseGroups()
        expenseGroups.value = res.data
    } catch (e) {
        console.error("Failed to fetch expense groups", e)
        notify.error("Failed to load expense groups")
    } finally {
        loading.value = false
    }
}

const openAddModal = () => {
    isEditing.value = false
    editingId.value = null
    form.value = {
        name: '',
        description: '',
        is_active: true,
        budget: 0,
        start_date: '',
        end_date: '',
        icon: ''
    }
    showModal.value = true
}

const openEditModal = (group: any) => {
    isEditing.value = true
    editingId.value = group.id
    form.value = {
        name: group.name,
        description: group.description || '',
        is_active: group.is_active,
        budget: group.budget || 0,
        start_date: group.start_date ? group.start_date.split('T')[0] : '',
        end_date: group.end_date ? group.end_date.split('T')[0] : '',
        icon: group.icon || ''
    }
    showModal.value = true
}

const getBudgetPercentage = (group: any) => {
    if (!group.budget || group.budget === 0) return 0
    return Math.min(100, ((group.total_spend || 0) / group.budget) * 100)
}

const getBudgetColor = (group: any) => {
    if (!group.budget) return 'text-gray-500'
    const pct = getBudgetPercentage(group)
    if (pct >= 100) return 'text-red-600'
    if (pct >= 80) return 'text-orange-500'
    return 'text-green-600'
}

const getBudgetColorCode = (group: any) => {
    if (!group.budget) return '#cbd5e1'
    const pct = getBudgetPercentage(group)
    if (pct >= 100) return '#ef4444'
    if (pct >= 80) return '#f97316'
    return '#10b981'
}

const handleSubmit = async () => {
    try {
        if (isEditing.value && editingId.value) {
            await financeApi.updateExpenseGroup(editingId.value, form.value)
            notify.success("Group updated successfully")
        } else {
            await financeApi.createExpenseGroup(form.value)
            notify.success("Group created successfully")
        }
        showModal.value = false
        fetchGroups()
    } catch (e) {
        notify.error("Failed to save group")
    }
}

const confirmDelete = (group: any) => {
    groupToDelete.value = group
    showDeleteConfirm.value = true
}

const doDelete = async () => {
    if (!groupToDelete.value) return
    try {
        await financeApi.deleteExpenseGroup(groupToDelete.value.id)
        notify.success("Group deleted")
        fetchGroups()
    } catch (e) {
        notify.error("Failed to delete group")
    } finally {
        showDeleteConfirm.value = false
        groupToDelete.value = null
    }
}

const formatDate = (dateStr: string) => {
    if (!dateStr) return '-'
    return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    })
}

const generateColor = (name: string) => {
    const colors = ['#eff6ff', '#f0fdf4', '#fef2f2', '#fff7ed', '#f0f9ff', '#faf5ff']
    const textColors = ['#1d4ed8', '#15803d', '#b91c1c', '#c2410c', '#0369a1', '#7e22ce']
    let hash = 0
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash)
    }
    const index = Math.abs(hash) % colors.length
    return { bg: colors[index], text: textColors[index] }
}

onMounted(() => {
    fetchGroups()
})
</script>

<style scoped>
/* Scoped Styles for tweaks */
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
    align-items: baseline;
    gap: 0.75rem;
}

.page-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: #111827;
    margin: 0;
}

.transaction-count {
    font-size: 0.875rem;
    color: #6b7280;
    font-weight: 400;
    background: transparent;
    padding: 0;
}

.header-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Filter Bar Style - Matches Transactions Filter Bar */
.filter-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
    padding: 0.625rem 1rem;
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    margin-bottom: 1.25rem;
}

.search-box-compact {
    position: relative;
    display: flex;
    align-items: center;
    width: auto;
    border: none;
    background: transparent;
    padding: 0;
}

.search-box-compact input {
    padding: 0.45rem 0.75rem 0.45rem 2rem;
    font-size: 0.8125rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
    background: white;
    width: 220px;
    outline: none;
    transition: all 0.2s;
}

.search-box-compact input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
    width: 240px;
}

.search-icon {
    position: absolute;
    left: 0.75rem;
    font-size: 0.8rem;
    color: #9ca3af;
    width: 0.9rem;
    height: 0.9rem;
}

.year-select {
    width: 140px;
}

.year-select :deep(.options-container) {
    min-width: 100%;
    right: 0;
    left: auto;
}

.btn-compact {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 0.875rem;
    font-size: 0.875rem;
    font-weight: 500;
    border-radius: 0.375rem;
    border: 1px solid transparent;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
}

.btn-compact.btn-primary {
    background-color: #4f46e5;
    color: white;
}

.btn-compact.btn-primary:hover {
    background-color: #4338ca;
}

.groups-container {
    padding: 0;
    /* Padding is already handled by MainLayout */
}

.groups-grid {
    display: grid;
    /* Use minmax 300px to allow more items per row on wider screens, filling space better */
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
}

.group-card-premium {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
    transition: all 0.3s;
    border: 1px solid rgba(255, 255, 255, 0.4);
}

.group-card-premium:hover {
    transform: translateY(-4px);
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02);
}

.group-card-premium.inactive {
    opacity: 0.7;
    filter: grayscale(0.5);
}

.group-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
}

.group-info h3 {
    font-size: 1.25rem;
    font-weight: 700;
    color: #1e293b;
    margin-bottom: 0.5rem;
}

.group-status {
    display: inline-flex;
    padding: 0.25rem 0.75rem;
    border-radius: 2rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.025em;
}

.group-status.active {
    background: #f0fdf4;
    color: #166534;
    border: 1px solid #bbf7d0;
}

.group-status.inactive {
    background: #f1f5f9;
    color: #475569;
    border: 1px solid #e2e8f0;
}

.group-actions {
    display: flex;
    gap: 0.5rem;
}

.group-desc {
    color: #475569;
    font-size: 0.95rem;
    line-height: 1.5;
    min-height: 3rem;
    margin-bottom: 0;
}

.group-budget-section {
    margin-top: 0.5rem;
    padding-top: 1rem;
    border-top: 1px dashed #e2e8f0;
}

.budget-info {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.5rem;
}

.progress-track {
    height: 8px;
    background: #f1f5f9;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 0.5rem;
}

.progress-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
}

.group-footer {
    padding-top: 1.25rem;
    border-top: 1px solid #f1f5f9;
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: #94a3b8;
    font-size: 0.85rem;
}

.expense-count {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #3b82f6;
    font-weight: 500;
}

.mini-icon {
    width: 0.9rem;
    height: 0.9rem;
}

/* Modal Styling Improvements */
.form-premium {
    padding: 1.5rem 0;
}

.form-input-premium {
    width: 100%;
    padding: 0.875rem 1.125rem;
    border-radius: 0.75rem;
    border: 1px solid #e2e8f0;
    background: #f8fafc;
    font-size: 1rem;
    transition: all 0.2s;
}

.form-input-premium:focus {
    background: white;
    border-color: #3b82f6;
    box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1);
}

.switch-premium {
    position: relative;
    display: inline-block;
    width: 52px;
    height: 28px;
}

.switch-premium input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #cbd5e1;
    transition: .4s;
}

.slider:before {
    position: absolute;
    content: "";
    height: 20px;
    width: 20px;
    left: 4px;
    bottom: 4px;
    background-color: white;
    transition: .4s;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

input:checked+.slider {
    background-color: #3b82f6;
}

input:checked+.slider:before {
    transform: translateX(24px);
}

.slider.round {
    border-radius: 28px;
}

.slider.round:before {
    border-radius: 50%;
}

.loading-state-premium {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 5rem 0;
    color: #64748b;
}

.loader-ring {
    width: 48px;
    height: 48px;
    border: 3px solid #e2e8f0;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 1.5rem;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.year-filter-wrapper {
    display: flex;
    align-items: center;
}

.form-row {
    display: flex;
    gap: 1rem;
}

.form-group.half {
    flex: 1;
}

.form-input-premium {
    width: 100%;
    padding: 0.875rem 1.125rem;
    border-radius: 0.75rem;
    border: 1px solid #e2e8f0;
    background: #f8fafc;
    font-size: 1rem;
    transition: all 0.2s;
    font-family: inherit;
}

textarea.form-input-premium {
    resize: vertical;
    min-height: 100px;
}

.empty-state-premium {
    min-height: 400px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    background: rgba(255, 255, 255, 0.5);
    border: 2px dashed #e2e8f0;
    border-radius: 1rem;
}

.empty-content h2 {
    font-size: 1.25rem;
    color: #64748b;
    font-weight: 500;
}

.link-action {
    color: #4f46e5;
    cursor: pointer;
    font-weight: 600;
    text-decoration: underline;
    text-decoration-thickness: 2px;
    text-underline-offset: 4px;
    transition: color 0.2s;
}


.link-action:hover {
    color: #4338ca;
}

/* --- Clean Modal Styles --- */
.compact-modal {
    max-width: 480px;
    padding: 0;
    overflow: hidden;
    background: #ffffff;
    border-radius: 1.25rem;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
}

.modal-header-clean {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 1.5rem 1.75rem 0.5rem;
    background: white;
}

.modal-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.2;
}

.modal-subtitle {
    font-size: 0.875rem;
    color: #64748b;
    margin-top: 0.25rem;
}

.btn-icon-circle-subtle {
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f1f5f9;
    border: none;
    color: #64748b;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-icon-circle-subtle:hover {
    background: #e2e8f0;
    color: #0f172a;
}

.form-premium-clean {
    padding: 1.5rem 1.75rem 1.75rem;
}

.form-label-clean {
    display: block;
    font-size: 0.8125rem;
    font-weight: 600;
    color: #475569;
    margin-bottom: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.02em;
}

.input-with-icon {
    position: relative;
    display: flex;
    align-items: center;
}

.input-icon {
    position: absolute;
    left: 1rem;
    color: #94a3b8;
    pointer-events: none;
}

.form-input-clean {
    width: 100%;
    padding: 0.75rem 1rem 0.75rem 2.75rem;
    border-radius: 0.75rem;
    border: 1px solid #e2e8f0;
    font-size: 0.95rem;
    color: #1e293b;
    background: #f8fafc;
    transition: all 0.2s;
}

.form-input-clean.textarea {
    padding-left: 1rem;
    resize: none;
}

.form-input-clean:focus {
    background: white;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    outline: none;
}

.grid-2-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

.toggle-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    cursor: pointer;
    transition: all 0.2s;
    height: 46px;
    /* Match input height roughly */
}

.toggle-card.active {
    background: #eff6ff;
    border-color: #bfdbfe;
    color: #1d4ed8;
}

.status-text {
    font-size: 0.875rem;
    font-weight: 600;
}

.toggle-switch-mini {
    width: 2rem;
    height: 1.125rem;
    background: #cbd5e1;
    border-radius: 99px;
    position: relative;
    transition: background 0.2s;
}

.toggle-switch-mini::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 0.875rem;
    height: 0.875rem;
    background: white;
    border-radius: 50%;
    transition: transform 0.2s;
}

.toggle-switch-mini.on {
    background: #3b82f6;
}

.toggle-switch-mini.on::after {
    transform: translateX(0.875rem);
}

.date-range-box {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 0.5rem 0.75rem;
    border-radius: 0.75rem;
}

.date-field {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.date-icon {
    color: #94a3b8;
}

.date-input-clean {
    border: none;
    background: transparent;
    font-size: 0.875rem;
    color: #334155;
    outline: none;
    width: 100%;
    font-family: inherit;
}

.date-arrow {
    color: #cbd5e1;
    font-weight: bold;
}

.modal-footer-clean {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    margin-top: 2rem;
    border-top: 1px solid #f1f5f9;
    padding-top: 1.25rem;
}

.btn-clean-secondary {
    padding: 0.625rem 1.25rem;
    border-radius: 0.5rem;
    font-weight: 600;
    color: #64748b;
    background: transparent;
    border: none;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-clean-secondary:hover {
    background: #f1f5f9;
    color: #0f172a;
}

.btn-clean-primary {
    padding: 0.625rem 1.5rem;
    border-radius: 0.5rem;
    font-weight: 600;
    color: white;
    background: #0f172a;
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    transition: all 0.2s;
}

.btn-clean-primary:hover {
    background: #1e293b;
    transform: translateY(-1px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}

/* --- Card V2 Modern Styles --- */
.group-card-modern {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
    height: 100%;
}

.group-card-modern:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 24px -8px rgba(0, 0, 0, 0.08), 0 4px 8px -4px rgba(0, 0, 0, 0.04);
    border-color: #cbd5e1;
}

.card-top-row {
    display: flex;
    align-items: center;
    gap: 0.875rem;
    margin-bottom: 1rem;
}

.group-icon-avat {
    width: 2.75rem;
    height: 2.75rem;
    border-radius: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.125rem;
    font-weight: 700;
    flex-shrink: 0;
}

.group-header-text {
    flex-grow: 1;
    min-width: 0;
}

.group-title {
    font-size: 1rem;
    font-weight: 700;
    color: #0f172a;
    margin-bottom: 0.125rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.group-meta-row {
    display: flex;
    align-items: center;
    gap: 0.35rem;
}

.status-dot-mini {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #cbd5e1;
}

.status-dot-mini.on {
    background: #10b981;
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
}

.status-label-mini {
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 500;
}

.card-actions-float {
    display: flex;
    gap: 0.25rem;
    opacity: 0;
    transform: translateX(10px);
    transition: all 0.2s ease;
}

.group-card-modern:hover .card-actions-float {
    opacity: 1;
    transform: translateX(0);
}

.action-btn-mini {
    width: 2rem;
    height: 2rem;
    border-radius: 0.5rem;
    border: 1px solid transparent;
    background: transparent;
    color: #64748b;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
}

.action-btn-mini:hover {
    background: #f1f5f9;
    color: #3b82f6;
}

.action-btn-mini.danger:hover {
    background: #fef2f2;
    color: #ef4444;
}

.card-body-modern {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
}

.card-desc-modern {
    font-size: 0.875rem;
    color: #64748b;
    line-height: 1.5;
    margin-bottom: 1.25rem;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 2.6rem;
}

.budget-box-modern {
    background: #f8fafc;
    border-radius: 0.75rem;
    padding: 0.875rem;
    margin-bottom: 1rem;
    border: 1px solid #f1f5f9;
}

.budget-header-modern {
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    color: #64748b;
    letter-spacing: 0.02em;
}

.progress-track-modern {
    height: 6px;
    background: #e2e8f0;
    border-radius: 99px;
    margin-bottom: 0.75rem;
    overflow: hidden;
}

.progress-fill-modern {
    height: 100%;
    border-radius: 99px;
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}

.budget-stats-grid {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.stat-item {
    display: flex;
    flex-direction: column;
}

.stat-lbl {
    font-size: 0.65rem;
    color: #94a3b8;
    text-transform: uppercase;
    font-weight: 700;
}

.stat-val {
    font-size: 0.875rem;
    font-weight: 700;
    color: #334155;
}

.stat-div {
    width: 1px;
    height: 20px;
    background: #e2e8f0;
}

.no-budget-badge-modern {
    background: #f8fafc;
    border: 1px dashed #e2e8f0;
    padding: 1rem;
    text-align: center;
    border-radius: 0.75rem;
    color: #94a3b8;
    font-size: 0.875rem;
    font-weight: 500;
    margin-bottom: 1rem;
}

.card-footer-modern {
    padding-top: 1rem;
    border-top: 1px solid #f1f5f9;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.8125rem;
    color: #64748b;
}

.footer-item {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-weight: 500;
}

.text-icon {
    color: #94a3b8;
}

/* --- Icon Selector Styles --- */
.icon-selector-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.5rem;
}

.icon-preview-large {
    width: 4rem;
    height: 4rem;
    border-radius: 1rem;
    background: #f8fafc;
    border: 1px dashed #cbd5e1;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    cursor: default;
}

.icon-presets {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    justify-content: center;
}

.emoji-btn {
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 0.5rem;
    border: 1px solid transparent;
    background: #f1f5f9;
    font-size: 1.25rem;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
}

.emoji-btn:hover {
    background: #e2e8f0;
    transform: scale(1.1);
}

.emoji-btn.selected {
    background: #eff6ff;
    border-color: #3b82f6;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.icon-input-hidden {
    border: none;
    background: transparent;
    border-bottom: 2px solid #e2e8f0;
    text-align: center;
    width: 60px;
    font-size: 1.25rem;
    padding: 0.25rem;
    outline: none;
}

.icon-input-hidden:focus {
    border-color: #3b82f6;
}

/* Delete Modal Styles */
.delete-icon-wrapper {
    background: #fef2f2;
    width: 64px;
    height: 64px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 1rem;
}

.btn-clean-msg-danger {
    padding: 0.625rem 1.25rem;
    background: #ef4444;
    color: white;
    border-radius: 0.5rem;
    font-weight: 600;
    transition: all 0.2s;
}

.btn-clean-msg-danger:hover {
    background: #dc2626;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(220, 38, 38, 0.2);
}
</style>
