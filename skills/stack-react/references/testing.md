# React testing snippets (Vitest + Testing Library)

## Component behavior
```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

it('AC1: adds an item and updates the total', async () => {
  render(<Cart initialItems={[]} />);
  await userEvent.click(screen.getByRole('button', { name: /add sample item/i }));
  expect(screen.getByRole('status')).toHaveTextContent('Total: R$ 10,00');
});
```
(`toHaveTextContent` needs `@testing-library/jest-dom` in the test setup — check the project's setup file.)

## Network with MSW
```tsx
import { http, HttpResponse } from 'msw';
import { server } from '../test/server';   // project's MSW server

it('AC2: shows an error when listings fail to load', async () => {
  server.use(http.get('/api/listings', () => new HttpResponse(null, { status: 500 })));
  render(<ListingsPage />);
  expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
});
```

## Hook
```ts
import { renderHook, act } from '@testing-library/react';

it('AC3: debounces the search term', () => {
  vi.useFakeTimers();
  const { result, rerender } = renderHook(({ term }) => useDebounced(term, 300), {
    initialProps: { term: '' },
  });
  rerender({ term: 'a' });
  act(() => vi.advanceTimersByTime(299));
  expect(result.current).toBe('');
  act(() => vi.advanceTimersByTime(1));
  expect(result.current).toBe('a');
});
```
