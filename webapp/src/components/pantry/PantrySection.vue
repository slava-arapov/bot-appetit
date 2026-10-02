<script setup lang="ts">
import type { PantryItem, PantryStatus } from '../../api/client'
import { isExpiring, STATUS_LABELS } from '../../utils/pantry'
import PantryItemRow from './PantryItemRow.vue'

defineProps<{
  status: PantryStatus
  items: PantryItem[]
  expiryWarningDays: number
}>()
defineEmits<{ cycle: [item: PantryItem]; edit: [item: PantryItem]; remove: [item: PantryItem] }>()
</script>

<template>
  <section class="section">
    <h2 class="section__title">
      {{ STATUS_LABELS[status] }}
      <span class="section__count">{{ items.length }}</span>
    </h2>
    <PantryItemRow
      v-for="item in items"
      :key="item.id"
      :item="item"
      :expiring="item.status !== 'to_buy' && isExpiring(item.expiry_date, expiryWarningDays)"
      @cycle="$emit('cycle', item)"
      @edit="$emit('edit', item)"
      @remove="$emit('remove', item)"
    />
  </section>
</template>

<style scoped>
.section {
  margin-bottom: 20px;
}

.section__title {
  margin: 0;
  padding: 8px 16px;
  color: var(--tg-hint);
  font-size: 14px;
  font-weight: 500;
}

.section__count {
  margin-left: 4px;
  font-variant-numeric: tabular-nums;
}
</style>
