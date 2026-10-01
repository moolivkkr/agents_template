package com.example.pbt;

import java.util.ArrayList;
import java.util.List;

// Harness stub: an application type the samples use but no sample defines.
public class Widget {
    private String name;
    private String description;
    private int priority;

    public Widget() {
    }

    public Widget(String name, String description) {
        this(name, description, 0);
    }

    public Widget(String name, String description, int priority) {
        this.name = name;
        this.description = description;
        this.priority = priority;
    }

    public String getName() { return name; }
    public String getDescription() { return description; }
    public int getPriority() { return priority; }

    public List<String> validate() {
        var errors = new ArrayList<String>();
        if (name == null || name.isEmpty() || name.length() > 255) errors.add("name");
        if (description != null && description.length() > 2000) errors.add("description");
        return errors;
    }
}
