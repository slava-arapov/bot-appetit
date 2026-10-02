<script setup lang="ts">
defineProps<{ name: 'pantry' | 'profile' | 'settings' | 'reset' }>()
</script>

<template>
  <svg
    class="icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-if="name === 'pantry'">
      <path d="M3 9h18l-2 11H5L3 9z" />
      <path d="M8 9l3-5M16 9l-3-5" />
    </template>
    <template v-else-if="name === 'profile'">
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
    </template>
    <template v-else-if="name === 'reset'">
      <path d="M4 12a8 8 0 1 0 3-6.2" />
      <path d="M4 4v5h5" />
    </template>
    <template v-else>
      <path d="M4 7h10M18 7h2M4 17h2M10 17h10" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="8" cy="17" r="2" />
    </template>
  </svg>
</template>

<style scoped>
.icon {
  width: 24px;
  height: 24px;
}
</style>
