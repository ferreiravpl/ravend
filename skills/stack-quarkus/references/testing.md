# Quarkus testing snippets (adapt to the project's style)

## API test (Dev Services provides the database)
```java
@QuarkusTest
class OrderResourceTest {

    @Test
    void createsOrder() {                       // AC1
        given().contentType(ContentType.JSON)
               .body("""
                     {"customerId": 7, "items": [{"sku": "A1", "qty": 2}]}""")
        .when().post("/orders")
        .then().statusCode(201)
               .body("items.size()", is(1));
    }

    @Test
    void returns400WhenItemsAreEmpty() {        // AC2
        given().contentType(ContentType.JSON).body("{\"customerId\": 7, \"items\": []}")
        .when().post("/orders")
        .then().statusCode(400);
    }
}
```

## Mocking a collaborator
```java
@QuarkusTest
class CheckoutResourceTest {
    @InjectMock PaymentGateway gateway;         // gateway must be @ApplicationScoped

    @Test
    void returns502WhenPaymentFails() {         // AC3
        Mockito.when(gateway.charge(any())).thenThrow(new GatewayException("down"));
        given().contentType(ContentType.JSON).body("{\"orderId\": 1}")
        .when().post("/checkout")
        .then().statusCode(502);
    }
}
```

## Transactional test data
```java
@QuarkusTest
class OrderRepositoryTest {
    @Inject OrderRepository repository;

    @Test
    @TestTransaction                            // rolled back after the test
    void findsOpenOrders() {
        repository.persist(new Order(/* ... */));
        assertThat(repository.findOpen()).hasSize(1);
    }
}
```

## Unit test (no Quarkus boot — fastest)
```java
class PriceCalculatorTest {
    @Test
    void appliesDiscountAboveThreshold() {      // AC4
        assertThat(new PriceCalculator().total(List.of(item(100), item(50)))).isEqualByComparingTo("135.00");
    }
}
```
