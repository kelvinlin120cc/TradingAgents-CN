<template>
  <div class="pulse-container">
    <!-- Header -->
    <div class="pulse-header">
      <h1>全球宏观预期概率面板</h1>
      <p class="subtitle">Polymarket + Kalshi 双源合并 · 资金背书的市场情绪温度计</p>
      <div class="header-actions">
        <el-button type="primary" :loading="refreshing" @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新数据
        </el-button>
        <span class="update-time" v-if="overview?.as_of">
          更新时间: {{ formatTime(overview.as_of) }}
        </span>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading && !overview" class="loading-state">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <p>正在加载全球宏观预期概率数据...</p>
    </div>

    <!-- Error State -->
    <div v-if="error && !overview" class="error-state">
      <el-icon class="error-icon"><WarningFilled /></el-icon>
      <p>{{ error }}</p>
      <el-button @click="handleRefresh">重新加载</el-button>
    </div>

    <!-- Main Content -->
    <div v-if="overview" class="pulse-content">
      <!-- Core Modules (Expanded) -->
      <div class="modules-section">
        <h2 class="section-title">核心模块</h2>
        <div class="modules-grid">
          <div 
            v-for="module in coreModules" 
            :key="module.key" 
            class="module-card"
          >
            <div class="module-header">
              <h3 class="module-title">{{ module.key }}</h3>
              <div class="module-meta">
                <span class="market-count">{{ module.market_count }} 个市场</span>
                <span class="volume">{{ formatVolume(module.volume_24h) }} 24h成交量</span>
              </div>
            </div>
            <div class="module-markets">
              <div 
                v-for="market in module.markets" 
                :key="market.question" 
                class="market-item"
                @click="showMarketDetail(market)"
              >
                <div class="market-prob">
                  <span class="prob-value" :class="getProbClass(market.prob_yes)">
                    {{ formatProb(market.prob_yes) }}
                  </span>
                </div>
                <div class="market-info">
                  <span class="market-question">{{ market.question }}</span>
                  <span class="market-change" v-if="market.change_24h">
                    {{ formatChange(market.change_24h) }}
                  </span>
                </div>
                <div class="market-source">
                  <el-tag :type="market.source === 'polymarket' ? 'success' : 'warning'" size="small">
                    {{ market.source }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Reference Modules (Collapsed) -->
      <div class="modules-section collapsed">
        <h2 class="section-title">参考模块</h2>
        <el-collapse v-model="activeCollapse">
          <el-collapse-item 
            v-for="module in referenceModules" 
            :key="module.key"
            :title="`${module.key} (${module.market_count})`"
            :name="module.key"
          >
            <div class="module-markets">
              <div 
                v-for="market in module.markets" 
                :key="market.question" 
                class="market-item"
                @click="showMarketDetail(market)"
              >
                <div class="market-prob">
                  <span class="prob-value" :class="getProbClass(market.prob_yes)">
                    {{ formatProb(market.prob_yes) }}
                  </span>
                </div>
                <div class="market-info">
                  <span class="market-question">{{ market.question }}</span>
                </div>
                <div class="market-source">
                  <el-tag :type="market.source === 'polymarket' ? 'success' : 'warning'" size="small">
                    {{ market.source }}
                  </el-tag>
                </div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>

    <!-- Market Detail Dialog -->
    <el-dialog 
      v-model="detailVisible" 
      :title="selectedMarket?.question"
      width="600px"
    >
      <div v-if="selectedMarket" class="market-detail">
        <div class="detail-row">
          <span class="label">概率:</span>
          <span class="value">{{ formatProb(selectedMarket.prob_yes) }}</span>
        </div>
        <div class="detail-row">
          <span class="label">24h变化:</span>
          <span class="value">{{ formatChange(selectedMarket.change_24h) || '无数据' }}</span>
        </div>
        <div class="detail-row">
          <span class="label">24h成交量:</span>
          <span class="value">{{ formatVolume(selectedMarket.volume_24h) }}</span>
        </div>
        <div class="detail-row">
          <span class="label">流动性:</span>
          <span class="value">{{ formatVolume(selectedMarket.liquidity) }}</span>
        </div>
        <div class="detail-row">
          <span class="label">到期日:</span>
          <span class="value">{{ selectedMarket.end_date || '无数据' }}</span>
        </div>
        <div class="detail-row">
          <span class="label">来源:</span>
          <el-tag :type="selectedMarket.source === 'polymarket' ? 'success' : 'warning'">
            {{ selectedMarket.source }}
          </el-tag>
        </div>
        <div v-if="selectedMarket.pick_label" class="detail-row">
          <span class="label">阈值:</span>
          <span class="value">{{ selectedMarket.pick_label }}</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Loading, WarningFilled } from '@element-plus/icons-vue'
import axios from 'axios'

interface Market {
  question: string
  question_zh?: string
  topic: string
  prob_yes: number | null
  change_24h: number | null
  change_7d: number | null
  volume_24h: number
  liquidity: number
  end_date?: string
  source: string
  pick_label?: string
  outcomes?: string[]
  prices?: number[]
}

interface Module {
  key: string
  core: boolean
  market_count: number
  volume_24h: number
  source_counts: Record<string, number>
  markets: Market[]
}

interface Overview {
  as_of: string
  sources: string[]
  module_order: string[]
  core_modules: string[]
  modules: Module[]
  updating?: boolean
}

const loading = ref(false)
const refreshing = ref(false)
const error = ref<string | null>(null)
const overview = ref<Overview | null>(null)
const detailVisible = ref(false)
const selectedMarket = ref<Market | null>(null)
const activeCollapse = ref<string[]>([])

const coreModules = computed(() => {
  return overview.value?.modules.filter(m => m.core) || []
})

const referenceModules = computed(() => {
  return overview.value?.modules.filter(m => !m.core) || []
})

const fetchData = async (force = false) => {
  loading.value = true
  error.value = null
  try {
    const response = await axios.get('/api/pulse/overview', {
      params: { refresh: force }
    })
    overview.value = response.data
    if (response.data.updating) {
      // Poll for update completion
      pollForUpdate()
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || '获取数据失败'
    if (error.value) {
      ElMessage.error(error.value)
    }
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const pollForUpdate = async () => {
  const currentAsOf = overview.value?.as_of
  let attempts = 0
  const maxAttempts = 30
  
  while (attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 2000))
    try {
      const response = await axios.get('/api/pulse/overview')
      if (response.data.as_of !== currentAsOf) {
        overview.value = response.data
        ElMessage.success('数据已更新')
        break
      }
    } catch (e) {
      // Continue polling on error
    }
    attempts++
  }
}

const handleRefresh = () => {
  refreshing.value = true
  fetchData(true)
}

const showMarketDetail = (market: Market) => {
  selectedMarket.value = market
  detailVisible.value = true
}

const formatProb = (prob: number | null) => {
  if (prob === null) return '无数据'
  return `${(prob * 100).toFixed(1)}%`
}

const formatChange = (change: number | null) => {
  if (change === null) return null
  const pct = change * 100
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

const formatVolume = (volume: number) => {
  if (!volume) return '$0'
  if (volume >= 1e6) return `$${(volume / 1e6).toFixed(1)}M`
  if (volume >= 1e3) return `$${(volume / 1e3).toFixed(1)}K`
  return `$${volume.toFixed(0)}`
}

const formatTime = (time: string) => {
  return new Date(time).toLocaleString('zh-CN')
}

const getProbClass = (prob: number | null) => {
  if (prob === null) return 'prob-unknown'
  if (prob >= 0.7) return 'prob-high'
  if (prob >= 0.4) return 'prob-medium'
  return 'prob-low'
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.pulse-container {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.pulse-header {
  margin-bottom: 24px;
}

.pulse-header h1 {
  font-size: 24px;
  margin-bottom: 8px;
}

.subtitle {
  color: #666;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.update-time {
  color: #999;
  font-size: 14px;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100px 20px;
  text-align: center;
}

.loading-icon,
.error-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-icon {
  color: #f56c6c;
}

.modules-section {
  margin-bottom: 32px;
}

.section-title {
  font-size: 18px;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}

.modules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 20px;
}

.module-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.module-header {
  padding: 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #eee;
}

.module-title {
  font-size: 16px;
  margin-bottom: 8px;
}

.module-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #666;
}

.module-markets {
  padding: 12px;
}

.market-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.market-item:hover {
  background: #f5f7fa;
}

.market-prob {
  width: 60px;
  text-align: center;
}

.prob-value {
  font-weight: bold;
  font-size: 16px;
}

.prob-high {
  color: #67c23a;
}

.prob-medium {
  color: #e6a23c;
}

.prob-low {
  color: #f56c6c;
}

.prob-unknown {
  color: #999;
}

.market-info {
  flex: 1;
  padding-left: 12px;
}

.market-question {
  display: block;
  font-size: 14px;
  line-height: 1.4;
}

.market-change {
  font-size: 12px;
  color: #666;
}

.market-source {
  margin-left: 12px;
}

.market-detail .detail-row {
  display: flex;
  padding: 8px 0;
  border-bottom: 1px solid #eee;
}

.market-detail .label {
  width: 100px;
  color: #666;
}

.market-detail .value {
  flex: 1;
}
</style>