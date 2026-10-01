package com.example.pbt;

import java.util.List;

// Harness stub: an application type the samples use but no sample defines.
public final class Paging {
    public static <T> PageResult<T> paginate(List<T> all, String cursor, int pageSize) {
        int from = cursor == null ? 0 : Integer.parseInt(cursor);
        int to = Math.min(all.size(), from + pageSize);
        return new PageResult<>(all.subList(from, to), to < all.size(), String.valueOf(to));
    }
}
