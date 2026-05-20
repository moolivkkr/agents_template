# Property-based testing patterns for robust input validation.

## What Is Property-Based Testing?
Property-based testing generates random inputs and verifies that invariants (properties) hold for all of them. Instead of testing specific examples, you test universal truths about your code.

**Example:** Instead of testing `sort([3, 1, 2]) == [1, 2, 3]`, test that for ALL lists: `sort(list)` produces a result where every element is <= the next element, and the result contains the same elements as the input.

## When to Use It
- **Serialization roundtrips:** `decode(encode(x)) == x` for all x
- **Parser robustness:** parser never crashes on arbitrary input
- **Mathematical properties:** commutativity, associativity, idempotency
- **Data transformations:** output always satisfies structural invariants
- **API contracts:** valid inputs always produce valid outputs; invalid inputs always produce errors
- **State machines:** sequences of operations leave the system in a valid state

## When NOT to Use It
- UI rendering (visual output is hard to express as properties)
- Integration tests with external services (too slow for many iterations)
- Simple CRUD with well-defined examples (table-driven tests are clearer)

## Go: testing/quick and gopter

### testing/quick (stdlib — simple cases)
```go
import "testing/quick"

func TestSortIdempotent(t *testing.T) {
    f := func(input []int) bool {
        sorted := Sort(input)
        doubleSorted := Sort(sorted)
        return reflect.DeepEqual(sorted, doubleSorted)
    }
    if err := quick.Check(f, nil); err != nil {
        t.Error(err)
    }
}
```

### gopter (full-featured)
```go
import (
    "github.com/leanovate/gopter"
    "github.com/leanovate/gopter/gen"
    "github.com/leanovate/gopter/prop"
)

func TestEncodeDecodeRoundtrip(t *testing.T) {
    properties := gopter.NewProperties(gopter.DefaultTestParameters())

    properties.Property("encode/decode roundtrip", prop.ForAll(
        func(name string, age int) bool {
            user := User{Name: name, Age: age}
            encoded, err := json.Marshal(user)
            if err != nil {
                return false
            }
            var decoded User
            if err := json.Unmarshal(encoded, &decoded); err != nil {
                return false
            }
            return user.Name == decoded.Name && user.Age == decoded.Age
        },
        gen.AlphaString(),
        gen.IntRange(0, 150),
    ))

    properties.TestingRun(t)
}

func TestPaginationProperties(t *testing.T) {
    properties := gopter.NewProperties(gopter.DefaultTestParameters())

    properties.Property("all items appear across pages", prop.ForAll(
        func(totalItems int, pageSize int) bool {
            if pageSize <= 0 {
                return true // skip invalid page sizes
            }
            items := makeItems(totalItems)
            var collected []Item
            var cursor string
            for {
                page := paginate(items, cursor, pageSize)
                collected = append(collected, page.Items...)
                if !page.HasMore {
                    break
                }
                cursor = page.Cursor
            }
            return len(collected) == len(items)
        },
        gen.IntRange(0, 1000),
        gen.IntRange(1, 100),
    ))

    properties.TestingRun(t)
}
```

## Python: Hypothesis

```python
from hypothesis import given, strategies as st, settings, assume

@given(st.text(min_size=1, max_size=255))
def test_encode_decode_roundtrip(name: str):
    encoded = encode(name)
    decoded = decode(encoded)
    assert decoded == name

@given(st.lists(st.integers()))
def test_sort_preserves_length(xs: list[int]):
    assert len(sorted(xs)) == len(xs)

@given(st.lists(st.integers(), min_size=1))
def test_sort_produces_ordered_output(xs: list[int]):
    result = sorted(xs)
    for i in range(len(result) - 1):
        assert result[i] <= result[i + 1]

# Custom strategy for domain objects
widget_strategy = st.fixed_dictionaries({
    "name": st.text(min_size=1, max_size=255, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
    "description": st.text(max_size=2000),
    "priority": st.integers(min_value=0, max_value=10),
    "status": st.sampled_from(["active", "draft", "archived"]),
})

@given(widget_strategy)
def test_widget_validation_accepts_valid_input(data: dict):
    widget = Widget(**data)
    errors = widget.validate()
    assert errors == []

@given(st.text())
def test_parser_never_crashes(raw_input: str):
    """Parser may return errors, but must never raise an exception."""
    try:
        result = parse(raw_input)
        assert result is not None or result is None  # any result is fine
    except ParseError:
        pass  # expected for invalid input
    # No other exception types should escape

# Use assume() to filter inputs
@given(st.emails())
@settings(max_examples=200)
def test_email_normalization_is_idempotent(email: str):
    assume(is_valid_email(email))
    normalized = normalize_email(email)
    double_normalized = normalize_email(normalized)
    assert normalized == double_normalized
```

## Java: jqwik

```java
import net.jqwik.api.*;
import net.jqwik.api.constraints.*;

class WidgetPropertyTests {

    @Property
    void encodeDecodeRoundtrip(@ForAll @StringLength(min = 1, max = 255) String name) {
        Widget widget = new Widget(name, "description");
        String json = objectMapper.writeValueAsString(widget);
        Widget decoded = objectMapper.readValue(json, Widget.class);
        Assertions.assertEquals(widget.getName(), decoded.getName());
    }

    @Property
    void sortPreservesAllElements(@ForAll List<@IntRange(min = -1000, max = 1000) Integer> list) {
        List<Integer> sorted = new ArrayList<>(list);
        Collections.sort(sorted);
        Assertions.assertEquals(list.size(), sorted.size());
        Assertions.assertTrue(sorted.containsAll(list));
    }

    @Property
    void paginationCoversAllItems(
            @ForAll @IntRange(min = 0, max = 500) int totalItems,
            @ForAll @IntRange(min = 1, max = 100) int pageSize) {
        List<Widget> all = generateWidgets(totalItems);
        List<Widget> collected = new ArrayList<>();
        String cursor = null;
        do {
            PageResult<Widget> page = paginate(all, cursor, pageSize);
            collected.addAll(page.items());
            cursor = page.hasMore() ? page.cursor() : null;
        } while (cursor != null);
        Assertions.assertEquals(totalItems, collected.size());
    }

    // Custom arbitrary for domain objects
    @Provide
    Arbitrary<Widget> validWidgets() {
        Arbitrary<String> names = Arbitraries.strings()
                .withCharRange('a', 'z').ofMinLength(1).ofMaxLength(255);
        Arbitrary<String> descriptions = Arbitraries.strings().ofMaxLength(2000);
        Arbitrary<Integer> priorities = Arbitraries.integers().between(0, 10);
        return Combinators.combine(names, descriptions, priorities)
                .as((name, desc, priority) -> new Widget(name, desc, priority));
    }

    @Property
    void validWidgetsPassValidation(@ForAll("validWidgets") Widget widget) {
        var errors = widget.validate();
        Assertions.assertTrue(errors.isEmpty());
    }
}
```

## Rust: proptest and quickcheck

### proptest (recommended — more expressive)
```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn encode_decode_roundtrip(name in "[a-zA-Z0-9 ]{1,255}") {
        let widget = Widget::new(&name);
        let encoded = serde_json::to_string(&widget).unwrap();
        let decoded: Widget = serde_json::from_str(&encoded).unwrap();
        prop_assert_eq!(widget.name, decoded.name);
    }

    #[test]
    fn sort_preserves_length(mut vec in prop::collection::vec(any::<i32>(), 0..1000)) {
        let original_len = vec.len();
        vec.sort();
        prop_assert_eq!(vec.len(), original_len);
    }

    #[test]
    fn sort_produces_ordered_output(mut vec in prop::collection::vec(any::<i32>(), 0..1000)) {
        vec.sort();
        for window in vec.windows(2) {
            prop_assert!(window[0] <= window[1]);
        }
    }

    #[test]
    fn pagination_covers_all_items(
        total in 0usize..500,
        page_size in 1usize..100,
    ) {
        let items: Vec<Widget> = (0..total).map(|i| Widget::new(&format!("w{i}"))).collect();
        let mut collected = Vec::new();
        let mut cursor = None;
        loop {
            let page = paginate(&items, cursor.as_deref(), page_size);
            collected.extend(page.items);
            if !page.has_more {
                break;
            }
            cursor = Some(page.cursor.unwrap());
        }
        prop_assert_eq!(collected.len(), total);
    }
}
```

### quickcheck (simpler API)
```rust
use quickcheck::{quickcheck, Arbitrary, Gen};

quickcheck! {
    fn encode_decode_roundtrip(name: String) -> bool {
        if name.is_empty() || name.len() > 255 {
            return true; // skip invalid inputs
        }
        let encoded = encode(&name);
        let decoded = decode(&encoded);
        decoded == name
    }
}
```

## TypeScript: fast-check

```typescript
import fc from "fast-check";

describe("Property-based tests", () => {
  test("encode/decode roundtrip", () => {
    fc.assert(
      fc.property(fc.string({ minLength: 1, maxLength: 255 }), (name) => {
        const widget = { name, description: "" };
        const encoded = JSON.stringify(widget);
        const decoded = JSON.parse(encoded);
        expect(decoded.name).toBe(name);
      }),
    );
  });

  test("sort preserves all elements", () => {
    fc.assert(
      fc.property(fc.array(fc.integer()), (arr) => {
        const sorted = [...arr].sort((a, b) => a - b);
        expect(sorted.length).toBe(arr.length);
        for (const item of arr) {
          expect(sorted).toContain(item);
        }
      }),
    );
  });

  test("sort produces ordered output", () => {
    fc.assert(
      fc.property(fc.array(fc.integer(), { minLength: 2 }), (arr) => {
        const sorted = [...arr].sort((a, b) => a - b);
        for (let i = 0; i < sorted.length - 1; i++) {
          expect(sorted[i]).toBeLessThanOrEqual(sorted[i + 1]);
        }
      }),
    );
  });

  test("pagination covers all items", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 500 }),
        fc.integer({ min: 1, max: 100 }),
        (totalItems, pageSize) => {
          const items = Array.from({ length: totalItems }, (_, i) => ({ id: i }));
          const collected: typeof items = [];
          let cursor: string | undefined;
          do {
            const page = paginate(items, cursor, pageSize);
            collected.push(...page.items);
            cursor = page.hasMore ? page.cursor : undefined;
          } while (cursor);
          expect(collected.length).toBe(totalItems);
        },
      ),
    );
  });
});
```

## Common Properties to Test

| Property | Description | Example |
|----------|-------------|---------|
| **Roundtrip** | `decode(encode(x)) == x` | Serialization, URL encoding, base64 |
| **Idempotency** | `f(f(x)) == f(x)` | Sort, normalize, format |
| **Commutativity** | `f(a, b) == f(b, a)` | Set union, addition |
| **Invariant preservation** | Output always satisfies constraint | Sorted list is ordered |
| **No crash** | Function never panics/throws on any input | Parsers, validators |
| **Completeness** | All input elements appear in output | Pagination, partitioning |
| **Monotonicity** | If input grows, output grows (or doesn't shrink) | Counting, accumulation |

## Rules
- Property tests complement example-based tests — they do not replace them
- Start with roundtrip properties — they catch the most bugs with least effort
- Use constrained generators (e.g., `IntRange(0, 150)`) to stay in valid input space
- Use `assume()` / `filter` sparingly — too much filtering wastes test iterations
- Set deterministic seeds in CI for reproducibility — random seeds in local dev
- If a property test finds a failure, add it as an explicit example test for regression
- 100-200 iterations per property is usually sufficient — more for parsers and serializers
