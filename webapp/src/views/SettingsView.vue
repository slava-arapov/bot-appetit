<script setup lang="ts">
import CookingTimeSegmented from '../components/settings/CookingTimeSegmented.vue'
import ServingsStepper from '../components/settings/ServingsStepper.vue'
import { SERVINGS_MAX, SERVINGS_MIN, useSettings } from '../composables/useSettings'

const { settings, loading, loadError, stepServings, setCookingTime, reload } = useSettings()
</script>

<template>
  <main class="page">
    <h1 class="page__title">Настройки</h1>

    <van-skeleton v-if="loading" :row="4" />

    <div v-else-if="loadError" class="state" role="alert">
      <p>Не удалось загрузить настройки</p>
      <button type="button" class="state__retry" data-test="reload" @click="reload">
        Повторить
      </button>
    </div>

    <template v-else-if="settings">
      <section class="setting">
        <h2 class="setting__label">Порции</h2>
        <ServingsStepper
          :value="settings.servings"
          :min="SERVINGS_MIN"
          :max="SERVINGS_MAX"
          @step="stepServings"
        />
      </section>

      <section class="setting">
        <h2 class="setting__label">Время на готовку</h2>
        <CookingTimeSegmented
          :model-value="settings.cooking_time"
          @update:model-value="setCookingTime"
        />
      </section>
    </template>
  </main>
</template>

<style scoped>
.setting {
  margin-bottom: 24px;
}

.setting__label {
  margin: 0 0 8px;
  color: var(--tg-hint);
  font-size: 14px;
  font-weight: 500;
}

.state {
  text-align: center;
}

.state__retry {
  min-width: var(--tap-size);
  min-height: var(--tap-size);
  padding: 0 20px;
  border: none;
  border-radius: var(--radius);
  background: var(--tg-button);
  color: var(--tg-button-text);
}
</style>
