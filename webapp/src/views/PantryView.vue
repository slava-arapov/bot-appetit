<script setup lang="ts">
import { ref } from 'vue'
import type { PantryChanges, PantryDraft, PantryItem } from '../api/client'
import PantryItemSheet from '../components/pantry/PantryItemSheet.vue'
import PantrySection from '../components/pantry/PantrySection.vue'
import { usePantry } from '../composables/usePantry'

const pantry = usePantry()
const { items, sections, expiryWarningDays, loading, loadError } = pantry

const sheetOpen = ref(false)
const editing = ref<PantryItem | null>(null)

function openAdd() {
  editing.value = null
  sheetOpen.value = true
}

function openEdit(item: PantryItem) {
  editing.value = item
  sheetOpen.value = true
}

/** Из формы правки уходит только то, что реально изменилось. */
function changesOf(item: PantryItem, draft: PantryDraft): PantryChanges {
  const changes: PantryChanges = {}
  if (draft.name !== item.name) changes.name = draft.name
  if (draft.status && draft.status !== item.status) changes.status = draft.status
  if (draft.quantity !== item.quantity) changes.quantity = draft.quantity
  if (draft.expiry_date !== item.expiry_date) changes.expiry_date = draft.expiry_date
  return changes
}

async function save(draft: PantryDraft) {
  const item = editing.value
  let saved = true
  if (!item) {
    saved = await pantry.add(draft)
  } else {
    const changes = changesOf(item, draft)
    if (Object.keys(changes).length > 0) saved = await pantry.update(item.id, changes)
  }
  // при ошибке форма остаётся открытой: введённое не пропадает
  if (saved) sheetOpen.value = false
}

function removeEditing() {
  if (editing.value) pantry.remove(editing.value)
  sheetOpen.value = false
}
</script>

<template>
  <main class="page">
    <header class="head">
      <h1 class="page__title head__title">Запасы</h1>
      <button type="button" class="head__add" aria-label="Добавить продукт" @click="openAdd">
        +
      </button>
    </header>

    <van-skeleton v-if="loading" :row="6" />

    <div v-else-if="loadError" class="state" role="alert">
      <p>Не удалось загрузить запасы</p>
      <button type="button" class="state__button" data-test="reload" @click="pantry.reload">
        Повторить
      </button>
    </div>

    <div v-else-if="items.length === 0" class="state">
      <p>Добавь первый продукт</p>
      <button type="button" class="state__button" data-test="empty-add" @click="openAdd">
        Добавить
      </button>
    </div>

    <template v-else>
      <PantrySection
        v-for="section in sections"
        :key="section.status"
        :status="section.status"
        :items="section.items"
        :expiry-warning-days="expiryWarningDays"
        @cycle="pantry.cycleStatus"
        @edit="openEdit"
        @remove="pantry.remove"
      />
    </template>

    <PantryItemSheet
      v-model:show="sheetOpen"
      :item="editing"
      @save="save"
      @remove="removeEditing"
    />
  </main>
</template>

<style scoped>
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.head__title {
  margin-bottom: 0;
}

.head__add {
  min-width: var(--tap-size);
  min-height: var(--tap-size);
  border: none;
  border-radius: 50%;
  background: var(--tg-button);
  color: var(--tg-button-text);
  font-size: 26px;
  line-height: 1;
}

.head__add:focus-visible,
.state__button:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}

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
</style>
