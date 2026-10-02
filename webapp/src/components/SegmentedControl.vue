<script setup lang="ts" generic="T extends string">
import { nextTick, ref } from 'vue'

const props = defineProps<{
  modelValue: T | null
  options: { value: T; label: string }[]
  label: string
}>()
const emit = defineEmits<{ 'update:modelValue': [value: T] }>()

const buttons = ref<HTMLButtonElement[]>([])

// В группу заходим одной точкой табуляции: на выбранном варианте или, если выбора нет, на первом.
function tabIndex(index: number) {
  const selected = props.options.findIndex((o) => o.value === props.modelValue)
  return index === Math.max(selected, 0) ? 0 : -1
}

function onKeydown(event: KeyboardEvent, index: number) {
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key]
  if (!step) return
  event.preventDefault()
  const next = (index + step + props.options.length) % props.options.length
  emit('update:modelValue', props.options[next].value)
  void nextTick(() => buttons.value[next]?.focus())
}
</script>

<template>
  <div class="segmented" role="radiogroup" :aria-label="label">
    <button
      v-for="(option, index) in options"
      :key="option.value"
      ref="buttons"
      type="button"
      role="radio"
      class="segmented__option"
      :aria-checked="modelValue === option.value"
      :tabindex="tabIndex(index)"
      @click="emit('update:modelValue', option.value)"
      @keydown="onKeydown($event, index)"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<style scoped>
.segmented {
  display: flex;
  gap: 4px;
  padding: 4px;
  border-radius: var(--radius);
  background: var(--tg-secondary-bg);
}

.segmented__option {
  flex: 1;
  min-height: var(--tap-size);
  border: none;
  border-radius: calc(var(--radius) - 4px);
  background: transparent;
  color: var(--tg-text);
  font-size: 15px;
}

.segmented__option[aria-checked='true'] {
  background: var(--tg-button);
  color: var(--tg-button-text);
}

.segmented__option:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: no-preference) {
  .segmented__option {
    transition: background-color 0.15s ease;
  }
}
</style>
