package snippet;

import org.springframework.boot.flyway.autoconfigure.FlywayAutoConfiguration;
import org.springframework.web.servlet.DispatcherServlet;

// Compiles only when the snippet's dependencies put Spring MVC and Spring Boot 4's Flyway auto-configuration
// (spring-boot-flyway: what runs the migrations at startup) on the classpath.
public class Probe {
    Class<?>[] used = {DispatcherServlet.class, FlywayAutoConfiguration.class};
}
