// Skill B7: one weighted curve, transform + opacity only.
export const EASE = [0.22, 1, 0.36, 1] as const

export const rise = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
  transition: { duration: 0.5, ease: EASE },
}
