# Anti-patterns — Spring

Segmento do índice mestre para stack Spring. Referência rápida para o reviewer.

---

## AP-1 — Field Injection
- **Padrão:** `@Autowired` em campo em vez de constructor injection
- **Severidade:** P1
- **Correção:** Constructor injection com `@RequiredArgsConstructor` ou constructor explícito
- **Freq:** 5 (hard constraint)

## AP-2 — findAll sem Pageable
- **Padrão:** `List<T>` sem paginação em método de repository/service
- **Severidade:** P1
- **Correção:** Retornar `Page<T>` com `Pageable`
- **Freq:** 4 (hard constraint)

## AP-4 — N+1 em relacionamento JPA
- **Padrão:** Acesso a coleção lazy em loop sem fetch join
- **Severidade:** P0
- **Correção:** `@EntityGraph` ou `JOIN FETCH` na query
- **Freq:** 3 (hard constraint)

## AP-3 — Catch genérico
- **Padrão:** `catch (Exception e)` sem contexto ou re-lançamento
- **Severidade:** P1
- **Correção:** Capturar exceção específica ou re-lançar como domain exception
- **Freq:** 6 (hard constraint)
