<script setup lang="ts">
import { computed, ref } from 'vue'
import { resetMemory, type ResetAction } from '../api/client'
import { haptic } from '../telegram/haptic'
import { useSnackbar } from '../composables/useSnackbar'

interface ResetOption {
  action: ResetAction
  title: string
  hint: string
  /** Текст подтверждения; без него действие выполняется сразу, как `reset:chat` в боте. */
  confirm?: string
  done: string
  danger?: boolean
}

const OPTIONS: ResetOption[] = [
  {
    action: 'chat',
    title: 'Забыть последние сообщения',
    hint: 'Бот начнёт разговор с чистого листа, профиль и запасы останутся',
    done: 'Переписка забыта 🧹',
  },
  {
    action: 'onboarding',
    title: 'Заполнить анкету заново',
    hint: 'Бот снова задаст вопросы о вкусах, порциях и технике',
    confirm:
      'Точно заполнить анкету заново? Текущие вкусы, ограничения и техника будут перезаписаны по ходу вопросов.',
    done: 'Анкета сброшена. Открой чат с ботом и напиши /start — он задаст первый вопрос 📋',
  },
  {
    action: 'all',
    title: 'Забыть всё и начать с начала',
    hint: 'Анкета, история, запасы и переписка будут удалены',
    confirm: 'Точно забыть всё — анкету, историю, запасы и переписку? Это нельзя отменить.',
    done: 'Всё забыто. Открой чат с ботом и напиши /start — начнём с начала 🔄',
    danger: true,
  },
]

const snackbar = useSnackbar()
const pending = ref<ResetOption | null>(null)
const busy = ref(false)
const doneMessage = ref<string | null>(null)

const confirmOpen = computed({
  get: () => pending.value !== null,
  set: (open: boolean) => {
    if (!open && !busy.value) pending.value = null
  },
})

async function run(option: ResetOption) {
  busy.value = true
  doneMessage.value = null
  try {
    await resetMemory(option.action)
    haptic.success()
    doneMessage.value = option.done
    pending.value = null
  } catch {
    haptic.error()
    pending.value = null
    snackbar.showError('Не удалось сбросить', () => void run(option))
  } finally {
    busy.value = false
  }
}

function choose(option: ResetOption) {
  if (busy.value) return
  if (option.confirm) pending.value = option
  else void run(option)
}
</script>

<template>
  <main class="page">
    <h1 class="page__title">Сброс</h1>

    <p v-if="doneMessage" class="done" role="status" data-test="done">{{ doneMessage }}</p>

    <ul class="options">
      <li v-for="option in OPTIONS" :key="option.action">
        <button
          type="button"
          class="option"
          :class="{ 'option--danger': option.danger }"
          :disabled="busy"
          :data-test="`reset-${option.action}`"
          @click="choose(option)"
        >
          <span class="option__title">{{ option.title }}</span>
          <span class="option__hint">{{ option.hint }}</span>
        </button>
      </li>
    </ul>

    <van-popup v-model:show="confirmOpen" position="bottom" round safe-area-inset-bottom>
      <div
        v-if="pending"
        class="sheet"
        role="alertdialog"
        aria-modal="true"
        aria-label="Подтверждение"
      >
        <h2 class="sheet__title">{{ pending.title }}</h2>
        <p class="sheet__text" data-test="confirm-text">{{ pending.confirm }}</p>
        <button
          type="button"
          class="sheet__confirm"
          :disabled="busy"
          data-test="confirm"
          @click="run(pending)"
        >
          Да, сбросить
        </button>
        <button type="button" class="sheet__cancel" data-test="cancel" @click="confirmOpen = false">
          Отмена
        </button>
      </div>
    </van-popup>
  </main>
</template>

<style scoped>
.options {
  display: flex;
  flex-direction: column;
  gap: var(--gap);
  margin: 0;
  padding: 0;
  list-style: none;
}

.option {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
  min-height: 72px;
  padding: 12px 16px;
  border: none;
  border-radius: var(--radius);
  background: var(--tg-secondary-bg);
  color: var(--tg-text);
  text-align: left;
}

.option--danger .option__title {
  color: var(--tg-destructive);
}

.option:disabled {
  opacity: 0.5;
}

.option:focus-visible,
.sheet button:focus-visible {
  outline: 2px solid var(--tg-button);
  outline-offset: 2px;
}

.option__title {
  font-size: 17px;
  font-weight: 500;
}

.option__hint {
  color: var(--tg-hint);
  font-size: 14px;
}

.done {
  margin: 0 0 16px;
  padding: 12px 16px;
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--tg-button) 15%, transparent);
}

.sheet {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 16px 16px;
  background: var(--tg-bg);
  color: var(--tg-text);
}

.sheet__title {
  margin: 0;
  font-size: 18px;
}

.sheet__text {
  margin: 0;
  color: var(--tg-hint);
}

.sheet__confirm,
.sheet__cancel {
  min-height: var(--tap-size);
  border: none;
  border-radius: var(--radius);
  font-size: 16px;
}

.sheet__confirm {
  background: var(--tg-destructive);
  color: var(--tg-button-text);
}

.sheet__confirm:disabled {
  opacity: 0.5;
}

.sheet__cancel {
  background: transparent;
  color: var(--tg-button);
}
</style>
