package com.example.pbt;

import java.util.List;

// Harness stub: an application type the samples use but no sample defines.
public record PageResult<T>(List<T> items, boolean hasMore, String cursor) {
}
