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

## Layer rules (ArchUnit)
```java
@AnalyzeClasses(packages = "com.example.orders", importOptions = ImportOption.DoNotIncludeTests.class)
class ArchitectureTest {
    @ArchTest
    static final ArchRule layers = layeredArchitecture().consideringAllDependencies()
        .layer("Domain").definedBy("..domain..")
        .layer("Application").definedBy("..application..")
        .layer("Adapters").definedBy("..adapter..")
        .whereLayer("Adapters").mayNotBeAccessedByAnyLayer()
        .whereLayer("Application").mayOnlyBeAccessedByLayers("Adapters")
        .whereLayer("Domain").mayOnlyBeAccessedByLayers("Application", "Adapters");

    @ArchTest
    static final ArchRule domainHasNoFramework = noClasses().that().resideInAPackage("..domain..")
        .should().dependOnClassesThat().resideInAnyPackage("io.quarkus..", "jakarta..", "org.hibernate..");
}
```

## Native integration test
```java
@QuarkusIntegrationTest                         // same tests as the @QuarkusTest subclass, against the native binary
class OrderResourceIT extends OrderResourceTest {}
```
`./mvnw verify -Dnative` (or `-Pnative`) builds the image and runs `*IT` against it; with Mandrel in a container: `-Dquarkus.native.container-build=true`.

## Injectable clock
```java
@ApplicationScoped
class ClockProducer { @Produces @DefaultBean Clock clock() { return Clock.systemUTC(); } }

@QuarkusTest
@TestProfile(FixedClockProfile.class)           // or @InjectMock Clock / a mutable test clock bean
class DeadlineJobTest { /* advance the clock, run the job, assert */ }
```
