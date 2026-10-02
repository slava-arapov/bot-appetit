<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Tag } from '../../api/client'
import { DEFAULT_EQUIPMENT, lowercaseInput, normalizeTag, sameValue } from '../../utils/profile'

const props = defineProps<{ tags: Tag[] }>()
const emit = defineEmits<{ toggle: [name: string]; add: [value: string] }>()

// Кастомные пункты, которые уже встречались на экране: выключенный остаётся в списке до перезагрузки.
const custom = ref<string[]>([])
const draft = ref('')

function remember(value: string) {
  const known = [...DEFAULT_EQUIPMENT, ...custom.value].some((name) => sameValue(name, value))
  if (!known) custom.value = [...custom.value, value]
}

watch(
  () => props.tags,
  (tags) => tags.forEach((tag) => remember(tag.value)),
  { immediate: true, deep: true },
)

const items = computed(() =>
  [...DEFAULT_EQUIPMENT, ...custom.value].map((name) => ({
    name,
    checked: props.tags.some((tag) => sameValue(tag.value, name)),
  })),
)

function addCustom() {
  const value = normalizeTag(draft.value)
  if (!value) return
  remember(value)
  emit('add', value)
  draft.value = ''
}
</script>

<template>
  <section class="group">
    <h2 class="group__title">Техника и посуда</h2>

    <ul class="list">
      <li v-for="item in items" :key="item.name">
        <label class="item" data-test="item">
          <input
            type="checkbox"
            class="item__box"
            :checked="item.checked"
            @change="emit('toggle', item.name)"
          />
          <span>{{ item.name }}</span>
        </label>
      </li>
    </ul>

    <form class="add" @submit.prevent="addCustom">
      <input
        :value="draft"
        autocapitalize="none"
        class="add__input"
        data-test="custom-input"
        maxlength="40"
        autocomplete="off"
        enterkeyhint="done"
        aria-label="Своя техника или посуда"
        placeholder="Своё…"
        @input="draft = lowercaseInput($event)"
      />
      <!-- обработчик на клике: Enter в поле браузер превращает в клик по этой кнопке -->
      <button
        type="submit"
        class="add__button"
        data-test="custom-add"
        :disabled="!draft.trim()"
        @click.prevent="addCustom"
      >
        + своё
      </button>
    </form>
  </section>
</template>

<style scoped>
.group {
  margin-bottom: 24px;
}

.group__title {
  margin: 0 0 8px;
  color: var(--tg-hint);
  font-size: 14px;
  font-weight: 500;
}

.list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 4px 12px;
  margin: 0 0 8px;
  padding: 0;
  list-style: none;
}

.item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: var(--tap-size);
}

.item__box {
  width: 22px;
  height: 22px;
  accent-color: var(--tg-button);
}

.add {
  display: flex;
  gap: 8px;
}

.add__input {
  flex: 1;
  min-width: 0;
  min-height: var(--tap-size);
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: var(--radius);
  background: var(--tg-secondary-bg);
  color: var(--tg-text);
  font: inherit;
}

.add__button {
  min-height: var(--tap-size);
  padding: 0 16px;
  border: none;
  border-radius: var(--radius);
  background: var(--tg-button);
  color: var(--tg-button-text);
}

.add__button:disabled {
  opacity: 0.4;
}

.add__input:focus-visible {
  border-color: var(--tg-button);
  outline: none;
}

.item__box:focus-visible,
.add__button:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}
</style>
