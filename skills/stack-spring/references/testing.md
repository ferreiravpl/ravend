# Spring testing snippets (adapt to the project's style)

## Unit (no context)
```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {
    @Mock OrderRepository repository;
    @InjectMocks OrderService service;

    @Test
    void rejectsOrderWithoutItems() {           // AC2
        var order = new CreateOrder(List.of());
        assertThatThrownBy(() -> service.create(order))
            .isInstanceOf(InvalidOrderException.class)
            .hasMessageContaining("items");
        verifyNoInteractions(repository);
    }
}
```

## Web slice
```java
@WebMvcTest(OrderController.class)
class OrderControllerTest {
    @Autowired MockMvc mvc;
    @MockitoBean OrderService service;          // Boot < 3.4: @MockBean

    @Test
    void returns404WhenOrderDoesNotExist() throws Exception {   // AC3
        given(service.find(42L)).willThrow(new OrderNotFoundException(42L));
        mvc.perform(get("/orders/42"))
           .andExpect(status().isNotFound())
           .andExpect(jsonPath("$.title").value("Order not found"));
    }
}
```

## Full API + real database (Testcontainers, Boot 3.1+)
```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class OrderApiIT {
    @Container @ServiceConnection
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16-alpine");

    @LocalServerPort int port;

    @Test
    void createsAndFetchesOrder() {             // AC1
        var id = given().port(port).contentType(JSON).body("""
                {"customerId": 7, "items": [{"sku": "A1", "qty": 2}]}""")
            .when().post("/orders")
            .then().statusCode(201).extract().jsonPath().getLong("id");

        given().port(port).when().get("/orders/{id}", id)
            .then().statusCode(200).body("items[0].qty", equalTo(2));
    }
}
```
Requires `org.testcontainers:postgresql`, `spring-boot-testcontainers`, `io.rest-assured:rest-assured` (test scope) — only add dependencies the developer agrees to; prefer what the project already has.

## Persistence slice
```java
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Testcontainers
class OrderRepositoryTest {
    @Container @ServiceConnection
    static PostgreSQLContainer<?> db = new PostgreSQLContainer<>("postgres:16-alpine");
    @Autowired OrderRepository repository;
    // assert queries, fetch joins, constraints
}
```
