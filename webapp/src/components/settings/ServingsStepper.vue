<script setup lang="ts">
defineProps<{ value: number | null; min: number; max: number }>()
const emit = defineEmits<{ step: [delta: 1 | -1] }>()
</script>

<template>
  <div class="stepper" role="group" aria-label="Количество порций">
    <button
      type="button"
      class="stepper__btn"
      aria-label="Меньше порций"
      :disabled="value === null || value <= min"
      @click="emit('step', -1)"
    >
      −
    </button>
    <output class="stepper__value" aria-live="polite">{{ value ?? '—' }}</output>
    <button
      type="button"
      class="stepper__btn"
      aria-label="Больше порций"
      :disabled="value !== null && value >= max"
      @click="emit('step', 1)"
    >
      +
    </button>
  </div>
</template>

<style scoped>
.stepper {
  display: inline-flex;
  align-items: center;
  gap: var(--gap);
}

.stepper__btn {
  min-width: var(--tap-size);
  min-height: var(--tap-size);
  border: none;
  border-radius: var(--radius);
  background: var(--tg-secondary-bg);
  color: var(--tg-text);
  font-size: 24px;
  line-height: 1;
}

.stepper__btn:active:not(:disabled) {
  background: var(--tg-button);
  color: var(--tg-button-text);
}

.stepper__btn:disabled {
  opacity: 0.4;
}

.stepper__btn:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}

.stepper__value {
  min-width: 2ch;
  text-align: center;
  font-size: 20px;
  font-variant-numeric: tabular-nums;
}
</style>
