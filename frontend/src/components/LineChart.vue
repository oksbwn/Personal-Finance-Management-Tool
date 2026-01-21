<template>
    <div class="line-chart-container">
        <svg :width="width" :height="height" :viewBox="`0 0 ${width} ${height}`">
            <!-- Grid lines -->
            <g class="grid">
                <line
                    v-for="i in 5"
                    :key="`h-${i}`"
                    :x1="padding.left"
                    :y1="padding.top + (chartHeight / 4) * (i - 1)"
                    :x2="width - padding.right"
                    :y2="padding.top + (chartHeight / 4) * (i - 1)"
                    stroke="#e5e7eb"
                    stroke-width="1"
                />
            </g>

            <!-- Gradient definition for area fill -->
            <defs>
                <linearGradient id="valueGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.15" />
                    <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.01" />
                </linearGradient>
            </defs>

            <!-- Area fill (smooth) -->
            <path
                v-if="paths.area"
                :d="paths.area"
                fill="url(#valueGradient)"
                stroke="none"
            />

            <!-- Value line (smooth) -->
            <path
                v-if="paths.value"
                :d="paths.value"
                fill="none"
                stroke="#3b82f6"
                stroke-width="2.5"
                stroke-linecap="round"
                stroke-linejoin="round"
            />

            <!-- Invested line (smooth dashed) -->
            <path
                v-if="paths.invested"
                :d="paths.invested"
                fill="none"
                stroke="#94a3b8"
                stroke-width="0.5"
                stroke-dasharray="5,5"
                stroke-linecap="round"
                stroke-linejoin="round"
            />

            <!-- Benchmark line (smooth dotted) -->
            <path
                v-if="paths.benchmark"
                :d="paths.benchmark"
                fill="none"
                stroke="#f59e0b"
                stroke-width="1.5"
                stroke-dasharray="2,3"
                stroke-linecap="round"
                stroke-linejoin="round"
                style="opacity: 0.6;"
            />

            <!-- Data points for interaction -->
            <g class="data-points">
                <circle
                    v-for="(point, index) in dataPoints"
                    :key="`point-${index}`"
                    :cx="point.x"
                    :cy="point.y"
                    r="2"
                    fill="#3b82f6"
                    class="hover-point"
                    @mouseenter="showTooltip(index, $event)"
                    @mouseleave="hideTooltip"
                />
            </g>

            <!-- Y-axis labels -->
            <g class="y-axis-labels">
                <text
                    v-for="(label, i) in yAxisLabels"
                    :key="`y-${i}`"
                    :x="padding.left - 10"
                    :y="padding.top + (chartHeight / 4) * i + 4"
                    text-anchor="end"
                    class="axis-label"
                >
                    {{ label }}
                </text>
            </g>

            <!-- X-axis labels -->
            <g class="x-axis-labels">
                <text
                    v-for="(label, i) in xAxisLabels"
                    :key="`x-${i}`"
                    :x="padding.left + (chartWidth / (xAxisLabels.length - 1)) * i"
                    :y="height - padding.bottom + 20"
                    text-anchor="middle"
                    class="axis-label"
                >
                    {{ label }}
                </text>
            </g>
        </svg>

        <!-- Legend -->
        <div class="chart-legend">
            <div class="legend-item">
                <div class="legend-line" style="background: #3b82f6;"></div>
                <span>Portfolio Value</span>
            </div>
            <div class="legend-item">
                <div class="legend-line dashed" style="background: #94a3b8;"></div>
                <span>Invested Amount</span>
            </div>
            <div v-if="props.benchmark && props.benchmark.length > 0" class="legend-item">
                <div class="legend-line dotted" style="background: #f59e0b;"></div>
                <span>Nifty 50 (Normalized)</span>
            </div>
        </div>

        <!-- Tooltip -->
        <div v-if="tooltip.visible" class="chart-tooltip" :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }">
            <div class="tooltip-date">{{ tooltip.date }}</div>
            <div class="tooltip-row">
                <span>Value:</span>
                <strong>{{ formatAmount(tooltip.value) }}</strong>
            </div>
            <div class="tooltip-row">
                <span>Invested:</span>
                <strong>{{ formatAmount(tooltip.invested) }}</strong>
            </div>
            <div class="tooltip-row gain" :class="tooltip.gain >= 0 ? 'positive' : 'negative'">
                <span>P/L:</span>
                <strong>{{ tooltip.gain >= 0 ? '+' : '' }}{{ formatAmount(tooltip.gain) }}</strong>
            </div>
            <div v-if="tooltip.benchmark" class="tooltip-row benchmark">
                <span>Nifty 50:</span>
                <strong>{{ formatAmount(tooltip.benchmark) }}</strong>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
    data: Array<{ date: string; value: number; invested: number }>
    benchmark?: Array<{ date: string; value: number }>
    height?: number
}>()

const width = 800
const height = props.height || 300
const padding = { top: 20, right: 20, bottom: 40, left: 60 }

const chartWidth = width - padding.left - padding.right
const chartHeight = height - padding.top - padding.bottom

const tooltip = ref({
    visible: false,
    x: 0,
    y: 0,
    date: '',
    value: 0,
    invested: 0,
    gain: 0,
    benchmark: 0
})

// Calculate scales
const maxValue = computed(() => {
    if (!props.data || props.data.length === 0) return 100
    
    let max = Math.max(...props.data.map(d => Math.max(d.value, d.invested)))
    
    if (props.benchmark && props.benchmark.length > 0) {
        const bMax = Math.max(...props.benchmark.map(b => b.value))
        max = Math.max(max, bMax)
    }
    
    return max
})

const minValue = computed(() => 0)

const yScale = (value: number) => {
    const range = maxValue.value - minValue.value
    if (range === 0) return chartHeight / 2
    return chartHeight - ((value - minValue.value) / range) * chartHeight
}

const xScale = (index: number) => {
    if (props.data.length <= 1) return chartWidth / 2
    return (index / (props.data.length - 1)) * chartWidth
}

// Helper to generate smooth SVG path (Cubic Bezier)
const getPathData = (dataPoints: { x: number; y: number }[]) => {
    if (dataPoints.length === 0) return ''
    if (dataPoints.length === 1) return `M ${dataPoints[0].x},${dataPoints[0].y}`

    let path = `M ${dataPoints[0].x},${dataPoints[0].y}`
    
    // Smoothing factor
    const smoothing = 0.2

    for (let i = 0; i < dataPoints.length - 1; i++) {
        const curr = dataPoints[i]
        const next = dataPoints[i + 1]
        
        // Control point calculation
        const prev = dataPoints[i - 1] || curr
        const nextNext = dataPoints[i + 2] || next

        const cp1x = curr.x + (next.x - prev.x) * smoothing
        const cp1y = curr.y + (next.y - prev.y) * smoothing
        const cp2x = next.x - (nextNext.x - curr.x) * smoothing
        const cp2y = next.y - (nextNext.y - curr.y) * smoothing

        path += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${next.x},${next.y}`
    }

    return path
}

// Generate path strings
const paths = computed(() => {
    if (!props.data || props.data.length === 0) {
        return { value: '', invested: '', area: '', benchmark: '' }
    }

    const valuePoints = props.data.map((d, i) => ({
        x: padding.left + xScale(i),
        y: padding.top + yScale(d.value)
    }))

    const investedPoints = props.data.map((d, i) => ({
        x: padding.left + xScale(i),
        y: padding.top + yScale(d.invested)
    }))

    const valuePath = getPathData(valuePoints)
    
    // Create area path by closing the value path to the bottom axis
    let areaPath = ''
    if (valuePoints.length > 0) {
        areaPath = valuePath + 
            ` L ${padding.left + xScale(valuePoints.length - 1)},${height - padding.bottom}` +
            ` L ${padding.left},${height - padding.bottom} Z`
    }

    // Benchmark path
    let benchmarkPath = ''
    if (props.benchmark && props.benchmark.length > 0) {
        const benchmarkPoints = props.benchmark.map((b, i) => ({
            x: padding.left + xScale(i),
            y: padding.top + yScale(b.value)
        }))
        benchmarkPath = getPathData(benchmarkPoints)
    }

    return { 
        value: valuePath, 
        invested: getPathData(investedPoints),
        area: areaPath,
        benchmark: benchmarkPath
    }
})

// Data points for interaction
const dataPoints = computed(() => {
    if (!props.data) return []
    return props.data.map((d, i) => ({
        x: padding.left + xScale(i),
        y: padding.top + yScale(d.value)
    }))
})

// Axis labels
const yAxisLabels = computed(() => {
    const range = maxValue.value - minValue.value
    const step = range / 4
    return Array.from({ length: 5 }, (_, i) => {
        const value = maxValue.value - (step * i)
        return formatAmount(value)
    })
})

const xAxisLabels = computed(() => {
    if (!props.data || props.data.length === 0) return []
    
    // Determine the total time span in days
    const firstDate = new Date(props.data[0].date)
    const lastDate = new Date(props.data[props.data.length - 1].date)
    const daysSpan = (lastDate.getTime() - firstDate.getTime()) / (1000 * 60 * 60 * 24)
    
    // For 800px width, ~6-8 labels is usually good
    const targetLabelCount = 6
    const step = Math.max(1, Math.floor(props.data.length / targetLabelCount))
    const labels: string[] = []
    
    props.data.forEach((d, i) => {
        // Show label for first, last, and every Nth point if it fits
        if (i === 0 || i === props.data.length - 1 || i % step === 0) {
            const date = new Date(d.date)
            
            if (daysSpan <= 95) { // ~3 months or less
                labels.push(date.toLocaleDateString('en-US', { day: 'numeric', month: 'short' }))
            } else if (daysSpan <= 366) { // ~1 year or less
                labels.push(date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' }))
            } else { // 'All' or long periods
                labels.push(date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }))
            }
        } else {
            labels.push('')
        }
    })
    
    // Final check for label overlap (very basic)
    // If the last label is too close to the previous non-empty label, hide the previous one
    let lastLabelIndex = -1
    for (let i = labels.length - 1; i >= 0; i--) {
        if (labels[i]) {
            if (lastLabelIndex !== -1 && (lastLabelIndex - i) < (step / 2)) {
                labels[i] = '' // Too crowded
            } else {
                lastLabelIndex = i
            }
        }
    }
    
    return labels
})

function formatAmount(value: number): string {
    if (value >= 10000000) return `₹${(value / 10000000).toFixed(2)}Cr`
    if (value >= 100000) return `₹${(value / 100000).toFixed(2)}L`
    if (value >= 1000) return `₹${(value / 1000).toFixed(1)}K`
    return `₹${value.toFixed(0)}`
}

function showTooltip(index: number, event: MouseEvent) {
    const dataPoint = props.data[index]
    tooltip.value = {
        visible: true,
        x: event.clientX + 10,
        y: event.clientY - 80,
        date: new Date(dataPoint.date).toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric', 
            year: 'numeric' 
        }),
        value: dataPoint.value,
        invested: dataPoint.invested,
        gain: dataPoint.value - dataPoint.invested,
        benchmark: props.benchmark ? props.benchmark[index]?.value : 0
    }
}

function hideTooltip() {
    tooltip.value.visible = false
}
</script>

<style scoped>
.line-chart-container {
    position: relative;
    width: 100%;
}

svg {
    width: 100%;
    height: auto;
}

.axis-label {
    font-size: 11px;
    fill: #64748b;
    font-weight: 500;
}

.hover-point {
    cursor: pointer;
    transition: r 0.2s;
}

.hover-point:hover {
    r: 5;
}

.chart-legend {
    display: flex;
    justify-content: center;
    gap: 2rem;
    margin-top: 1rem;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    color: #475569;
}

.legend-line {
    width: 24px;
    height: 3px;
    border-radius: 2px;
}

.legend-line.dashed {
    background: repeating-linear-gradient(
        to right,
        #94a3b8 0,
        #94a3b8 5px,
        transparent 5px,
        transparent 10px
    );
}

.chart-tooltip {
    position: fixed;
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.75rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    pointer-events: none;
    z-index: 1000;
    min-width: 160px;
}

.tooltip-date {
    font-size: 0.75rem;
    color: #64748b;
    margin-bottom: 0.5rem;
    font-weight: 600;
}

.tooltip-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.875rem;
    margin-bottom: 0.25rem;
}

.tooltip-row span {
    color: #64748b;
}

.tooltip-row.gain.positive strong {
    color: #10b981;
}

.tooltip-row.gain.negative strong {
    color: #ef4444;
}
</style>
