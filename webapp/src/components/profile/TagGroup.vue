<script setup lang="ts">
import { ref } from 'vue'
import type { Tag } from '../../api/client'
import { lowercaseInput, normalizeTag } from '../../utils/profile'

defineProps<{ title: string; tags: Tag[] }>()
const emit = defineEmits<{ add: [value: string]; remove: [tag: Tag] }>()

const draft = ref('')

function submit() {
  const value = normalizeTag(draft.value)
  if (!value) return
  emit('add', value)
  draft.value = ''
}
</script>

<template>
  <section class="group">
    <h2 class="group__title">{{ title }}</h2>

    <p v-if="tags.length === 0" class="group__empty">Пока ничего не добавлено</p>
    <ul v-else class="chips">
      <li v-for="tag in tags" :key="tag.id" class="chip">
        <span data-test="tag" class="chip__text">{{ tag.value }}</span>
        <button
          type="button"
          class="chip__remove"
          :aria-label="`Удалить ${tag.value}`"
          @click="emit('remove', tag)"
        >
          ×
        </button>
      </li>
    </ul>

    <form class="add" @submit.prevent="submit">
      <input
        :value="draft"
        autocapitalize="none"
        class="add__input"
        data-test="input"
        maxlength="40"
        autocomplete="off"
        enterkeyhint="done"
        :aria-label="`Добавить: ${title}`"
        placeholder="Добавить…"
        @input="draft = lowercaseInput($event)"
      />
      <!-- обработчик на клике: Enter в поле браузер превращает в клик по этой кнопке -->
      <button
        type="submit"
        class="add__button"
        data-test="add"
        aria-label="Добавить"
        :disabled="!draft.trim()"
        @click.prevent="submit"
      >
        +
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

.group__empty {
  margin: 0 0 8px;
  color: var(--tg-hint);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 8px;
  padding: 0;
  list-style: none;
}

.chip {
  display: inline-flex;
  align-items: center;
  min-height: var(--tap-size);
  padding-left: 14px;
  border-radius: 999px;
  background: var(--tg-secondary-bg);
}

.chip__remove {
  min-width: var(--tap-size);
  min-height: var(--tap-size);
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--tg-hint);
  font-size: 20px;
  line-height: 1;
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
  min-width: var(--tap-size);
  min-height: var(--tap-size);
  border: none;
  border-radius: var(--radius);
  background: var(--tg-button);
  color: var(--tg-button-text);
  font-size: 22px;
}

.add__button:disabled {
  opacity: 0.4;
}

.add__input:focus-visible {
  border-color: var(--tg-button);
  outline: none;
}

.chip__remove:focus-visible,
.add__button:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}
</style>
