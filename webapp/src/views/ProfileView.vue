<script setup lang="ts">
import EquipmentChecklist from '../components/profile/EquipmentChecklist.vue'
import TagGroup from '../components/profile/TagGroup.vue'
import { useProfile } from '../composables/useProfile'

const profile = useProfile()
const { tags, loading, loadError } = profile
</script>

<template>
  <main class="page">
    <h1 class="page__title">Профиль</h1>

    <van-skeleton v-if="loading" :row="6" />

    <div v-else-if="loadError" class="state" role="alert">
      <p>Не удалось загрузить профиль</p>
      <button type="button" class="state__button" data-test="reload" @click="profile.reload()">
        Повторить
      </button>
    </div>

    <template v-else>
      <!-- порядок: то, что чаще всего влияет на выбор рецепта, — выше -->
      <TagGroup
        title="Ограничения"
        :tags="tags.restrictions"
        @add="profile.add('restrictions', $event)"
        @remove="profile.remove('restrictions', $event)"
      />
      <EquipmentChecklist
        :tags="tags.equipment"
        @toggle="profile.toggleEquipment"
        @add="profile.add('equipment', $event)"
      />
      <TagGroup
        title="Любит"
        :tags="tags.likes"
        @add="profile.add('likes', $event)"
        @remove="profile.remove('likes', $event)"
      />
      <TagGroup
        title="Не любит"
        :tags="tags.dislikes"
        @add="profile.add('dislikes', $event)"
        @remove="profile.remove('dislikes', $event)"
      />
    </template>
  </main>
</template>

<style scoped>
.state {
  padding: 48px 0;
  text-align: center;
}

.state__button {
  min-height: var(--tap-size);
  padding: 0 24px;
  border: none;
  border-radius: var(--radius);
  background: var(--tg-button);
  color: var(--tg-button-text);
}

.state__button:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}
</style>
