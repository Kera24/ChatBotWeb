# Design Principles

Primary source: `docs/05_Design/01_Design_System.md`

This file updates the product design direction for AI agents. Expressionism is now the major design principle.

## Design mandate

The product must not feel like a generic SaaS dashboard.

It should feel:

- Expressive
- Bold
- Emotional
- Human
- Memorable
- Professional
- Usable
- Accessible
- Trustworthy

The audience includes colleges, agencies, healthcare providers, and business clients. Expression must strengthen trust, not reduce it.

## What Expressionism means here

Expressionism means the interface should communicate character and confidence through composition, hierarchy, language, motion, color, illustration, empty states, and microinteractions.

It does not mean clutter, novelty for its own sake, inaccessible contrast, confusing layouts, or decorative noise.

## Product personality

The platform should feel like an intelligent operating room for client knowledge: sharp, alive, confident, and warm. It should reveal the emotional stakes of the work: helping real people get correct answers from organisations they trust.

## Practical UI rules

- Use strong information hierarchy.
- Give important states visual weight.
- Make source grounding, confidence, and fallback behavior highly legible.
- Use expressive but controlled color, rhythm, spacing, and motion.
- Make empty states useful and emotionally human.
- Keep dashboards efficient for repeated operational work.
- Use accessible contrast, keyboard navigation, focus states, and screen-reader labels.
- Avoid generic admin-panel layouts when a more memorable composition can remain usable.
- Avoid decorative graphics that do not clarify product meaning.

## Do not do

- Do not build beige, blue-gray, or purple-gradient generic SaaS pages by default.
- Do not hide AI uncertainty.
- Do not make trust-critical screens feel playful or vague.
- Do not use animation that slows work or harms accessibility.
- Do not let client branding break readability or core UX.

## Required design review questions

Before shipping UI, ask:

1. Does this screen feel specific to Yoranix, or could it belong to any SaaS dashboard?
2. Does the expression serve comprehension and trust?
3. Can a busy client admin complete the workflow quickly?
4. Are sources, status, errors, and AI limits visible?
5. Is the screen accessible on keyboard, mobile, and assistive tech?

## Scope reminder

Do not build UI from this `.ai/` task. Encode the principle here so future UI implementation follows it.
