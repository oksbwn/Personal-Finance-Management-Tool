<script setup lang="ts">
import { ref, onMounted } from 'vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { financeApi } from '@/api/client'

const metrics = ref({
    net_worth: 0,
    monthly_spending: 0,
    currency: 'INR'
})

onMounted(async () => {
    try {
        const res = await financeApi.getMetrics()
        metrics.value = res.data
    } catch (e) {
        console.error("Failed to load metrics", e)
    }
})
</script>

<template>
  <MainLayout>
    <div class="dashboard-header">
      <h1>Dashboard</h1>
      <div class="date-display">{{ new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) }}</div>
    </div>
      
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-icon income">💰</div>
            <div class="stat-content">
                <h3>Net Worth</h3>
                <p class="amount">{{ metrics.currency }} {{ metrics.net_worth.toFixed(2) }}</p>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon expense">📉</div>
            <div class="stat-content">
                <h3>Monthly Spending</h3>
                <p class="amount">{{ metrics.currency }} {{ metrics.monthly_spending.toFixed(2) }}</p>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon investment">📈</div>
            <div class="stat-content">
                <h3>Investments</h3>
                <p class="amount">₹ 0.00</p>
            </div>
        </div>
    </div>
  </MainLayout>
</template>

<style scoped>
.dashboard-header {
    margin-bottom: 1.25rem;
}
h1 {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-main);
}
.date-display {
    color: var(--color-text-muted);
    margin-top: var(--spacing-xs);
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 0.875rem;
}

.stat-card {
    background: var(--color-surface);
    padding: 1rem;
    border-radius: 0.875rem; /* Softer corners */
    box-shadow: var(--shadow-sm);
    border: 1px solid var(--color-border);
    transition: transform 0.2s, box-shadow 0.2s;
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
}
.stat-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

.stat-icon {
    width: 40px; height: 40px;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.25rem;
    background: var(--color-background);
}
.income { background: #ecfdf5; color: #10b981; }
.expense { background: #fef2f2; color: #ef4444; }
.investment { background: #eff6ff; color: #3b82f6; }

.stat-content h3 {
    color: var(--color-text-muted);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.25rem;
}
.amount {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--color-text-main);
    letter-spacing: -0.02em;
}
</style>
