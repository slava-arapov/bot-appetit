<script setup lang="ts">
import { useMe } from '../composables/useMe'

const { me, error } = useMe()
</script>

<template>
  <main>
    <h1>Bot Appetit</h1>
    <!-- TODO: убрать после появления реальных подписей карточек хаба; пока — проверка сквозной цепочки -->
    <p v-if="me">user_id: {{ me.user_id }}</p>
    <p v-else-if="error">Ошибка API: {{ error }}</p>
    <p v-else>Загрузка…</p>
    <nav>
      <RouterLink to="/pantry">Pantry</RouterLink>
      <RouterLink to="/profile">Профиль</RouterLink>
      <RouterLink to="/settings">Настройки</RouterLink>
    </nav>
  </main>
</template>
