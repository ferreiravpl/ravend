# Event-driven test patterns (adapt names to the project's kit)

## Contract: producer matches the golden fixture
```java
class OrderConfirmedContractTest {
    @Test
    void serializesLikeTheFixture() throws Exception {
        var clock = Clock.fixed(Instant.parse("2026-01-01T00:00:00Z"), ZoneOffset.UTC);
        var event = OrderEvents.confirmed(order(), clock, fixedId());
        String json = mapper.writeValueAsString(event);
        JSONAssert.assertEquals(read("contracts/order.confirmed.v1.json"), json, JSONCompareMode.STRICT);
    }

    @Test
    void consumerIgnoresUnknownFields() throws Exception {
        var event = mapper.readValue(read("contracts/order.confirmed.v1.extra-field.json"), OrderConfirmed.class);
        assertThat(event.orderId()).isEqualTo(ORDER_ID);
    }
}
```

## Async: duplicate and out-of-order (real DB, explicit delivery)
```java
@QuarkusTest                                    // Spring: @SpringBootTest + Testcontainers @ServiceConnection
class PaymentConfirmedConsumerTest {
    @Inject PaymentConfirmedConsumer consumer;  // call the handler directly: no broker timing in the test
    @Inject OrderRepository orders;

    @Test
    void duplicateMessageHasOneEffect() {
        var msg = message(uuid(), "order-1");
        consumer.handle(msg);
        consumer.handle(msg);
        assertThat(orders.find("order-1").status()).isEqualTo(PAID);
        assertThat(outbox.eventsOfType("order.paid")).hasSize(1);
    }

    @Test
    void olderSnapshotIsIgnored() {
        consumer.handle(snapshot("order-1", version(3)));
        consumer.handle(snapshot("order-1", version(2)));
        assertThat(localCopy.find("order-1").version()).isEqualTo(3);
    }
}
```

## Async: two replicas at once
```java
@Test
void onlyOneReplicaReservesTheLastItem() throws Exception {
    var start = new CountDownLatch(1);
    Callable<Boolean> reserve = () -> { start.await(); return service.reserve("sku-1", customer()); };
    var pool = Executors.newFixedThreadPool(2);
    var a = pool.submit(reserve); var b = pool.submit(reserve);
    start.countDown();
    assertThat(List.of(a.get(), b.get())).containsExactlyInAnyOrder(true, false);
}
```

## Jobs with a controllable clock
```java
@Test
void unpaidOrderIsCancelledWhenTheDeadlinePasses() {
    var order = service.create(request());                     // schedules the timeout job in the same tx
    clock.advance(Duration.ofMinutes(16));                     // test clock bean, never Instant.now()
    jobs.runDue();                                             // harness runs due jobs synchronously
    assertThat(orders.find(order.id()).status()).isEqualTo(CANCELLED);
    jobs.runDue();                                             // running again is a no-op
    assertThat(outbox.eventsOfType("order.closed")).hasSize(1);
}
```

## Failure classification (retry vs dead-letter)
```java
@Test
void transientErrorIsRetriedAndPermanentGoesToDlq() {
    gateway.failNextWith(new TimeoutException());
    assertThat(consumer.handle(msg)).isEqualTo(Outcome.RETRY_LATER);
    assertThat(consumer.handle(invalidPayload())).isEqualTo(Outcome.DEAD_LETTER);
}
```

## Migration compatible with the previous version
```java
@Test
void previousVersionInsertStillWorks() {
    flyway.migrate();                                          // all migrations, fresh container
    jdbc.update("insert into orders(id, status) values (?, ?)", id, "CREATED");   // old app's insert
    assertThat(jdbc.queryForObject("select priority from orders where id = ?", Integer.class, id)).isEqualTo(0);
}
```
