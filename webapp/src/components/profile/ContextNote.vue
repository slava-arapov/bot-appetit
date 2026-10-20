<script setup lang="ts">
import { computed } from 'vue'
import type { CurrentContext } from '../../api/client'
import { formatContextDate } from '../../utils/profile'

const props = defineProps<{ context: CurrentContext }>()
const emit = defineEmits<{ clear: [] }>()

const updated = computed(() => formatContextDate(props.context.updated))
</script>

<template>
  <section class="note">
    <h2 class="note__title">Что бот сейчас помнит</h2>

    <p v-if="!context.notes" class="note__empty">Пока ничего</p>
    <div v-else class="note__card">
      <p data-test="notes" class="note__text">{{ context.notes }}</p>
      <div class="note__footer">
        <span v-if="updated" data-test="updated" class="note__date">обновлено {{ updated }}</span>
        <button type="button" class="note__clear" data-test="clear" @click="emit('clear')">
          Очистить
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.note {
  margin-bottom: 24px;
}

.note__title {
  margin: 0 0 8px;
  color: var(--tg-hint);
  font-size: 14px;
  font-weight: 500;
}

.note__empty {
  margin: 0;
  color: var(--tg-hint);
}

.note__card {
  padding: 12px 14px 4px;
  border-radius: var(--radius);
  background: var(--tg-secondary-bg);
}

.note__text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.note__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.note__date {
  color: var(--tg-hint);
  font-size: 13px;
}

.note__clear {
  min-height: var(--tap-size);
  margin-left: auto;
  padding: 0 4px;
  border: none;
  background: transparent;
  color: var(--tg-destructive);
  font: inherit;
}

.note__clear:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}
</style>
