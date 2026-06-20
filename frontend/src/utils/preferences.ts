/**
 * 用户偏好设置工具
 * 用于在 localStorage 中保存和恢复用户的配置选择
 */

const STORAGE_KEY_PREFIX = 'tradingagents_'

/**
 * 获取存储的偏好设置
 */
export function getPreference<T = any>(key: string, defaultValue: T): T {
  try {
    const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${key}`)
    if (stored === null || stored === undefined) {
      return defaultValue
    }
    return JSON.parse(stored) as T
  } catch (error) {
    console.error(`[Preferences] 读取 ${key} 失败:`, error)
    return defaultValue
  }
}

/**
 * 保存偏好设置
 */
export function setPreference<T = any>(key: string, value: T): void {
  try {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${key}`, JSON.stringify(value))
  } catch (error) {
    console.error(`[Preferences] 保存 ${key} 失败:`, error)
  }
}

/**
 * 清除指定偏好设置
 */
export function removePreference(key: string): void {
  try {
    localStorage.removeItem(`${STORAGE_KEY_PREFIX}${key}`)
  } catch (error) {
    console.error(`[Preferences] 清除 ${key} 失败:`, error)
  }
}

/**
 * 清除所有偏好设置
 */
export function clearAllPreferences(): void {
  try {
    const keys: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.startsWith(STORAGE_KEY_PREFIX)) {
        keys.push(key)
      }
    }
    keys.forEach((key: string) => localStorage.removeItem(key))
  } catch (error) {
    console.error('[Preferences] 清除所有偏好失败:', error)
  }
}

// 预定义的偏好键
export const PREFERENCE_KEYS = {
  QUICK_ANALYSIS_MODEL: 'quick_analysis_model',
  DEEP_ANALYSIS_MODEL: 'deep_analysis_model',
  ANALYSIS_DEPTH: 'analysis_depth',
  MARKET_TYPE: 'market_type',
  RESEARCH_DEPTH: 'research_depth'
} as const
