package com.example.pbt;

import java.util.ArrayList;
import java.util.List;

// Harness stub: an application type the samples use but no sample defines.
public final class TestData {
    public static List<Widget> generateWidgets(int n) {
        var out = new ArrayList<Widget>();
        for (int i = 0; i < n; i++) out.add(new Widget("w" + i, "d"));
        return out;
    }
}
