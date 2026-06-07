# Anti-patterns — Quarkus

Segmento do índice mestre para stack Quarkus. Referência rápida para o reviewer.

---

## AP-5 — @Singleton sem CDI proxy
- **Padrão:** `@Singleton` em bean que precisa de proxy CDI
- **Severidade:** P1
- **Correção:** Usar `@ApplicationScoped`
- **Freq:** 3 (hard constraint)

## AP-6 — Blocking no event loop
- **Padrão:** Operação blocking em endpoint reactive/vertx
- **Severidade:** P0
- **Correção:** Adicionar `@Blocking` ou migrar para cliente reactive
- **Freq:** 3 (hard constraint)

## AP-7 — persist sem @Transactional
- **Padrão:** Escrita em repository/service sem `@Transactional`
- **Severidade:** P0
- **Correção:** Adicionar `@Transactional` no método ou classe
- **Freq:** 4 (hard constraint)

## AP-3 — Catch genérico
- **Padrão:** `catch (Exception e)` sem contexto ou re-lançamento
- **Severidade:** P1
- **Correção:** Capturar exceção específica ou re-lançar como domain exception
- **Freq:** 6 (hard constraint)
