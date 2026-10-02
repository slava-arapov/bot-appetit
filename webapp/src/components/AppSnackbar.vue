<script setup lang="ts">
import { useSnackbar } from '../composables/useSnackbar'

const { current, act } = useSnackbar()
</script>

<template>
  <div v-if="current" class="snackbar" :role="current.kind === 'error' ? 'alert' : 'status'">
    <span class="snackbar__message">{{ current.message }}</span>
    <button type="button" class="snackbar__action" @click="act">{{ current.label }}</button>
  </div>
</template>

<style scoped>
.snackbar {
  position: fixed;
  right: var(--gap);
  bottom: calc(var(--gap) + env(safe-area-inset-bottom));
  left: var(--gap);
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--gap);
  padding: 4px 4px 4px 16px;
  border-radius: var(--radius);
  background: var(--tg-text);
  color: var(--tg-bg);
}

.snackbar__action {
  min-width: var(--tap-size);
  min-height: var(--tap-size);
  padding: 0 12px;
  border: none;
  background: transparent;
  color: inherit;
  font-weight: 600;
  text-decoration: underline;
}

.snackbar__action:focus-visible {
  outline: 2px solid var(--tg-bg);
  outline-offset: -2px;
}
</style>
