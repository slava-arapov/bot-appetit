<script setup lang="ts">
import { computed } from 'vue'
import HubIcon from '../components/HubIcon.vue'
import { useSummary } from '../composables/useSummary'
import { pantrySubtitle, profileSubtitle, settingsSubtitle } from '../utils/summary'

const { summary, loading } = useSummary()

const cards = computed(
  () =>
    [
      {
        to: '/pantry',
        icon: 'pantry',
        title: 'Запасы',
        subtitle: summary.value && pantrySubtitle(summary.value.pantry),
      },
      {
        to: '/profile',
        icon: 'profile',
        title: 'Профиль',
        subtitle: summary.value && profileSubtitle(summary.value.profile),
      },
      {
        to: '/settings',
        icon: 'settings',
        title: 'Настройки',
        subtitle: summary.value && settingsSubtitle(summary.value.settings),
      },
    ] as const,
)
</script>

<template>
  <main class="page">
    <h1 class="page__title">Bot Appetit</h1>
    <nav class="cards" aria-label="Разделы">
      <RouterLink v-for="card in cards" :key="card.to" :to="card.to" class="card">
        <span class="card__icon"><HubIcon :name="card.icon" /></span>
        <span class="card__text">
          <span class="card__title" data-test="title">{{ card.title }}</span>
          <!-- без сводки (ошибка загрузки) подписи просто нет: карточка остаётся рабочей -->
          <span v-if="card.subtitle" class="card__subtitle" data-test="subtitle">{{
            card.subtitle
          }}</span>
          <span
            v-else-if="loading"
            class="card__subtitle card__subtitle--placeholder"
            data-test="subtitle-placeholder"
            aria-hidden="true"
          />
        </span>
      </RouterLink>
    </nav>
  </main>
</template>

<style scoped>
.cards {
  display: flex;
  flex-direction: column;
  gap: var(--gap);
}

.card {
  display: flex;
  align-items: center;
  gap: 16px;
  min-height: 72px;
  padding: 12px 16px;
  border-radius: var(--radius);
  background: var(--tg-secondary-bg);
  color: var(--tg-text);
  text-decoration: none;
}

.card:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}

.card__icon {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--tg-button) 15%, transparent);
  color: var(--tg-button);
}

.card__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.card__title {
  font-size: 17px;
  font-weight: 500;
}

.card__subtitle {
  color: var(--tg-hint);
  font-size: 14px;
}

.card__subtitle--placeholder {
  width: 9em;
  height: 14px;
  margin-top: 4px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--tg-hint) 25%, transparent);
}

@media (prefers-reduced-motion: no-preference) {
  .card__subtitle--placeholder {
    animation: pulse 1.2s ease-in-out infinite;
  }
}

@keyframes pulse {
  50% {
    opacity: 0.5;
  }
}
</style>
