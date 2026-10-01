package snippet;

import org.springframework.web.servlet.DispatcherServlet;

// Compiles only when the catalog's library resolves (Spring MVC).
public class Probe {
    Class<?> used = DispatcherServlet.class;
}
