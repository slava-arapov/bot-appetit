<script setup lang="ts">
import { computed } from 'vue'
import type { PantryItem } from '../../api/client'
import { formatExpiry, STATUS_LABELS } from '../../utils/pantry'

const props = defineProps<{ item: PantryItem; expiring: boolean }>()
defineEmits<{ cycle: []; edit: []; remove: [] }>()

const expiryText = computed(() => {
  const date = props.item.expiry_date
  if (!date) return null
  // подсветка не должна держаться только на цвете, поэтому меняется и текст
  return props.expiring ? `истекает ${formatExpiry(date)}` : `годен до ${formatExpiry(date)}`
})

const meta = computed(() => [props.item.quantity, expiryText.value].filter(Boolean).join(' · '))
const label = computed(() => STATUS_LABELS[props.item.status])
</script>

<template>
  <van-swipe-cell>
    <div class="row">
      <button type="button" class="row__open" data-test="open" @click="$emit('edit')">
        <span class="row__name">{{ item.name }}</span>
        <span v-if="meta" class="row__meta" :class="{ 'row__meta--warn': expiring }">{{
          meta
        }}</span>
      </button>
      <button
        type="button"
        class="row__chip"
        data-test="status-chip"
        :data-status="item.status"
        :aria-label="`${item.name}: ${label}. Нажмите, чтобы сменить статус`"
        @click="$emit('cycle')"
      >
        {{ label }}
      </button>
    </div>
    <template #right>
      <button type="button" class="row__delete" data-test="swipe-delete" @click="$emit('remove')">
        Удалить
      </button>
    </template>
  </van-swipe-cell>
</template>

<style scoped>
.row {
  display: flex;
  align-items: center;
  gap: var(--gap);
  min-height: 56px;
  padding: 0 16px;
  background: var(--tg-bg);
}

.row__open {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
  min-height: var(--tap-size);
  padding: 4px 0;
  border: none;
  background: transparent;
  color: var(--tg-text);
  text-align: left;
}

.row__name {
  max-width: 100%;
  overflow: hidden;
  font-size: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row__meta {
  color: var(--tg-hint);
  font-size: 13px;
}

.row__meta--warn {
  color: var(--tg-destructive);
  font-weight: 600;
}

.row__chip {
  min-width: var(--tap-size);
  min-height: var(--tap-size);
  padding: 0 12px;
  border: 1.5px solid var(--status-color);
  border-radius: 999px;
  background: color-mix(in srgb, var(--status-color) 12%, transparent);
  color: var(--status-color);
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
}

.row__chip[data-status='have'] {
  --status-color: var(--status-have);
}

.row__chip[data-status='low'] {
  --status-color: var(--status-low);
}

.row__chip[data-status='to_buy'] {
  --status-color: var(--status-buy);
}

.row__open:focus-visible,
.row__chip:focus-visible,
.row__delete:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}

.row__delete {
  height: 100%;
  min-width: 88px;
  border: none;
  background: var(--tg-destructive);
  color: #fff;
  font-size: 15px;
}
</style>
