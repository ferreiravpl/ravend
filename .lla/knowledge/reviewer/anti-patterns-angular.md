# Anti-patterns — Angular

Segmento do índice mestre para stack Angular. Referência rápida para o reviewer.

---

## AP-8 — Subscribe sem cleanup
- **Padrão:** Subscrição manual sem gerenciar Subscription/destroy
- **Severidade:** P1
- **Correção:** Usar `async` pipe ou `takeUntil(destroy$)` com `OnDestroy`
- **Freq:** 5 (hard constraint)

## AP-9 — Uso de `any`
- **Padrão:** Tipagem com `any` em vez de tipo específico
- **Severidade:** P1
- **Correção:** Definir interface ou type específico
- **Freq:** 4 (hard constraint)

## AP-10 — DOM direto
- **Padrão:** Manipulação direta de DOM via `document.querySelector` ou `nativeElement`
- **Severidade:** P1
- **Correção:** Usar binding, ViewChild, Renderer2 ou diretiva
- **Freq:** 3 (hard constraint)
