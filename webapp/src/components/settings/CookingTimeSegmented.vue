<script setup lang="ts">
import type { CookingTime } from '../../api/client'
import SegmentedControl from '../SegmentedControl.vue'

defineProps<{ modelValue: CookingTime | null }>()
defineEmits<{ 'update:modelValue': [value: CookingTime] }>()

const OPTIONS: { value: CookingTime; label: string }[] = [
  { value: '15', label: '15 мин' },
  { value: '30', label: '30 мин' },
  { value: '60', label: '60 мин' },
  { value: 'any', label: 'Не важно' },
]
</script>

<template>
  <SegmentedControl
    :model-value="modelValue"
    :options="OPTIONS"
    label="Время на готовку"
    @update:model-value="$emit('update:modelValue', $event)"
  />
</template>
