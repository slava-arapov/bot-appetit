<script setup lang="ts">
import { computed } from 'vue'
import type { PantryItem, PantryStatus } from '../../api/client'
import { useBackClose } from '../../telegram/backButton'
import { SECTION_ORDER, STATUS_LABELS } from '../../utils/pantry'

const props = defineProps<{ show: boolean; item: PantryItem | null }>()
const emit = defineEmits<{ 'update:show': [value: boolean]; select: [status: PantryStatus] }>()

useBackClose(
  () => props.show,
  () => emit('update:show', false),
)

// Текущий статус отмечен галочкой в тексте: выбор не должен держаться только на цвете.
const actions = computed(() =>
  SECTION_ORDER.map((status) => ({
    name: props.item?.status === status ? `✓ ${STATUS_LABELS[status]}` : STATUS_LABELS[status],
    status,
    className: `status-action status-action--${status}`,
  })),
)

function pick(action: { status: PantryStatus }) {
  emit('select', action.status)
}
</script>

<template>
  <van-action-sheet
    :show="show"
    :actions="actions"
    :title="item?.name"
    cancel-text="Отмена"
    close-on-click-action
    safe-area-inset-bottom
    @update:show="emit('update:show', $event)"
    @select="pick"
  />
</template>

<style>
/* Классы действий Vant вешает на элементы вне scoped-области компонента. */
.status-action--have {
  color: var(--status-have);
}

.status-action--low {
  color: var(--status-low);
}

.status-action--to_buy {
  color: var(--status-buy);
}
</style>
