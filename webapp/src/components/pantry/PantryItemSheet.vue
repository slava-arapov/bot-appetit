<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { PantryDraft, PantryItem, PantryStatus } from '../../api/client'
import { STATUS_LABELS } from '../../utils/pantry'
import SegmentedControl from '../SegmentedControl.vue'

const props = defineProps<{ show: boolean; item: PantryItem | null }>()
const emit = defineEmits<{
  'update:show': [value: boolean]
  save: [draft: PantryDraft]
  remove: []
}>()

// В форме статусы идут в «естественном» порядке, как в цикле чипа: есть → мало → нужно купить.
const STATUS_OPTIONS = (['have', 'low', 'to_buy'] as const).map((value) => ({
  value,
  label: STATUS_LABELS[value],
}))

const name = ref('')
const quantity = ref('')
const expiry = ref('')
const status = ref<PantryStatus>('have')
const nameInput = ref<HTMLInputElement | null>(null)

const title = computed(() => (props.item ? 'Редактировать' : 'Новый продукт'))
const canSubmit = computed(() => name.value.trim().length > 0)

watch(
  () => props.show,
  (open) => {
    if (!open) return
    name.value = props.item?.name ?? ''
    quantity.value = props.item?.quantity ?? ''
    expiry.value = props.item?.expiry_date ?? ''
    status.value = props.item?.status ?? 'have'
    // клавиатуру поднимаем только при добавлении: при правке она закрыла бы половину формы
    if (!props.item) void nextTick(() => nameInput.value?.focus())
  },
  { immediate: true },
)

function submit() {
  if (!canSubmit.value) return
  emit('save', {
    name: name.value.trim(),
    status: status.value,
    quantity: quantity.value.trim() || null,
    expiry_date: expiry.value || null,
  })
}
</script>

<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    safe-area-inset-bottom
    @update:show="emit('update:show', $event)"
  >
    <form
      class="sheet"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
      @submit.prevent="submit"
    >
      <h2 class="sheet__title">{{ title }}</h2>

      <label class="field">
        <span class="field__label">Название</span>
        <input
          ref="nameInput"
          v-model="name"
          class="field__input"
          data-test="name"
          maxlength="80"
          autocomplete="off"
          required
        />
      </label>

      <div class="field">
        <span class="field__label">Статус</span>
        <SegmentedControl v-model="status" :options="STATUS_OPTIONS" label="Статус" />
      </div>

      <div class="sheet__row">
        <label class="field">
          <span class="field__label">Количество</span>
          <input
            v-model="quantity"
            class="field__input"
            data-test="quantity"
            maxlength="40"
            autocomplete="off"
            placeholder="2 пачки"
          />
        </label>
        <label class="field">
          <span class="field__label">Годен до</span>
          <input v-model="expiry" class="field__input" data-test="expiry" type="date" />
        </label>
      </div>

      <!-- обработчик на клике: браузер превращает Enter в поле в клик по этой кнопке -->
      <button
        type="submit"
        class="sheet__submit"
        data-test="submit"
        :disabled="!canSubmit"
        @click.prevent="submit"
      >
        {{ item ? 'Сохранить' : 'Добавить' }}
      </button>
      <button
        v-if="item"
        type="button"
        class="sheet__delete"
        data-test="delete"
        @click="emit('remove')"
      >
        Удалить
      </button>
    </form>
  </van-popup>
</template>

<style scoped>
.sheet {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 16px 16px;
  background: var(--tg-bg);
  color: var(--tg-text);
}

.sheet__title {
  margin: 0;
  font-size: 18px;
}

.sheet__row {
  display: flex;
  gap: var(--gap);
}

.sheet__row .field {
  flex: 1;
  min-width: 0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  color: var(--tg-hint);
  font-size: 14px;
}

.field__input {
  min-height: var(--tap-size);
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: var(--radius);
  background: var(--tg-secondary-bg);
  color: var(--tg-text);
  font: inherit;
}

.field__input:focus-visible {
  border-color: var(--tg-button);
  outline: none;
}

.sheet__submit,
.sheet__delete {
  min-height: var(--tap-size);
  border: none;
  border-radius: var(--radius);
  font-size: 16px;
}

.sheet__submit {
  background: var(--tg-button);
  color: var(--tg-button-text);
}

.sheet__submit:disabled {
  opacity: 0.4;
}

.sheet__delete {
  background: transparent;
  color: var(--tg-destructive);
}

.sheet__submit:focus-visible,
.sheet__delete:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}
</style>
