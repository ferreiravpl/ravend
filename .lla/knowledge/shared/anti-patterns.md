# Anti-patterns — Índice Mestre

Anti-patterns cross-stack detectados em reviews. Cada entrada tem ID, padrão, stack, severidade, correção e frequência.

**Regra de frequência:** freq ≥ 3 → hard constraint (equivalente a P0 na review).

---

## AP-1 — Field Injection

| Campo | Valor |
|-------|-------|
| **Padrão** | Uso de `@Autowired` em campo em vez de constructor injection |
| **Stack** | spring |
| **Severidade** | P1 |
| **Correção** | Usar constructor injection com `@RequiredArgsConstructor` ou constructor explícito |
| **Frequência** | 5 |
| **Exemplo** | `@Autowired private FooService fooService;` → `private final FooService fooService;` + constructor |

## AP-2 — findAll sem Pageable

| Campo | Valor |
|-------|-------|
| **Padrão** | Método de repository/service que retorna `List<T>` sem paginação |
| **Stack** | spring |
| **Severidade** | P1 |
| **Correção** | Retornar `Page<T>` com `Pageable` como parâmetro |
| **Frequência** | 4 |
| **Exemplo** | `List<Product> findAll()` → `Page<Product> findAll(Pageable pageable)` |

## AP-3 — Catch genérico

| Campo | Valor |
|-------|-------|
| **Padrão** | `catch (Exception e)` que engole ou loga sem contexto |
| **Stack** | java-generic |
| **Severidade** | P1 |
| **Correção** | Capturar exceção específica ou re-lançar como domain exception com contexto |
| **Frequência** | 6 |
| **Exemplo** | `catch (Exception e) { log.error(e); }` → `catch (SpecificException e) { throw new DomainException("context", e); }` |

## AP-4 — N+1 em relacionamento JPA

| Campo | Valor |
|-------|-------|
| **Padrão** | Acesso a coleção lazy em loop sem fetch join ou EntityGraph |
| **Stack** | spring |
| **Severidade** | P0 |
| **Correção** | Usar `@EntityGraph` ou `JOIN FETCH` na query |
| **Frequência** | 3 |
| **Exemplo** | `order.getItems().forEach(...)` em loop → `SELECT o FROM Order o JOIN FETCH o.items` |

## AP-5 — @Singleton sem CDI proxy

| Campo | Valor |
|-------|-------|
| **Padrão** | Uso de `@Singleton` em bean CDI que precisa de proxy (conversação, scope custom) |
| **Stack** | quarkus |
| **Severidade** | P1 |
| **Correção** | Usar `@ApplicationScoped` que suporta proxy CDI |
| **Frequência** | 3 |
| **Exemplo** | `@Singleton public class FooService` → `@ApplicationScoped public class FooService` |

## AP-6 — Blocking no event loop

| Campo | Valor |
|-------|-------|
| **Padrão** | Operação blocking (JDBC, IO, Thread.sleep) em endpoint reactive/vertx |
| **Stack** | quarkus |
| **Severidade** | P0 |
| **Correção** | Usar `@Blocking` ou migrar para cliente reactive |
| **Frequência** | 3 |
| **Exemplo** | `@GET public List<Foo> list()` com JDBC blocking → `@GET @Blocking public List<Foo> list()` |

## AP-7 — persist sem @Transactional

| Campo | Valor |
|-------|-------|
| **Padrão** | Operação de escrita em repository/service sem anotação transacional |
| **Stack** | quarkus |
| **Severidade** | P0 |
| **Correção** | Adicionar `@Transactional` no método ou classe |
| **Frequência** | 4 |
| **Exemplo** | `void save(Foo foo) { em.persist(foo); }` → `@Transactional void save(Foo foo) { em.persist(foo); }` |

## AP-8 — Subscribe sem cleanup

| Campo | Valor |
|-------|-------|
| **Padrão** | Subscrição manual de Observable sem gerenciar Subscription/destroy |
| **Stack** | angular |
| **Severidade** | P1 |
| **Correção** | Usar `async` pipe no template ou `takeUntil(destroy$)` com `OnDestroy` |
| **Frequência** | 5 |
| **Exemplo** | `this.service.getData().subscribe(data => ...)` → `data$ = this.service.getData();` + `{{ data$ | async }}` |

## AP-9 — Uso de `any`

| Campo | Valor |
|-------|-------|
| **Padrão** | Tipagem com `any` em vez de tipo específico |
| **Stack** | angular |
| **Severidade** | P1 |
| **Correção** | Definir interface ou type específico |
| **Frequência** | 4 |
| **Exemplo** | `data: any` → `data: ProductResponse` |

## AP-10 — DOM direto

| Campo | Valor |
|-------|-------|
| **Padrão** | Manipulação direta de DOM via `document.querySelector` ou `nativeElement` sem necessidade |
| **Stack** | angular |
| **Severidade** | P1 |
| **Correção** | Usar binding do Angular, ViewChild, Renderer2 ou diretiva |
| **Frequência** | 3 |
| **Exemplo** | `document.getElementById('foo').style.color = 'red'` → `[style.color]="color"` no template |
