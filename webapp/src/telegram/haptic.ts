// Не все клиенты Telegram дают HapticFeedback — без него вибро-отклик просто пропускается.
const feedback = () => window.Telegram?.WebApp?.HapticFeedback

export const haptic = {
  success: () => feedback()?.notificationOccurred('success'),
  error: () => feedback()?.notificationOccurred('error'),
}
