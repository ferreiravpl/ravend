# Angular testing snippets (Vitest syntax; Jasmine: `jasmine.createSpy`, `toBeTrue`; Jest: `jest.fn`)

## Service with HTTP
```ts
describe('OrderService', () => {
  let service: OrderService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(OrderService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('AC1: loads orders of the customer', async () => {
    const result = firstValueFrom(service.byCustomer(7));
    http.expectOne('/api/orders?customerId=7').flush([{ id: 1, total: 10 }]);
    expect(await result).toEqual([{ id: 1, total: 10 }]);
  });
});
```

## Standalone component
```ts
describe('OrderListComponent', () => {
  it('AC2: shows empty state when there are no orders', async () => {
    await TestBed.configureTestingModule({
      imports: [OrderListComponent],
      providers: [{ provide: OrderService, useValue: { byCustomer: () => of([]) } }],
    }).compileComponents();

    const fixture = TestBed.createComponent(OrderListComponent);
    fixture.componentRef.setInput('customerId', 7);   // signal/@Input
    fixture.detectChanges();
    await fixture.whenStable();

    expect(fixture.nativeElement.textContent).toContain('No orders yet');
  });
});
```

## Form validation
```ts
it('AC3: disables submit while email is invalid', async () => {
  const fixture = TestBed.createComponent(SignupComponent);
  fixture.detectChanges();
  const input: HTMLInputElement = fixture.nativeElement.querySelector('input[name=email]');
  input.value = 'not-an-email';
  input.dispatchEvent(new Event('input'));
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('button[type=submit]').disabled).toBe(true);
});
```
