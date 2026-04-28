# Kubernetes patterns for container orchestration and production deployments.

## Deployment (stateless services)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels: { app: api }
  template:
    metadata:
      labels: { app: api }
    spec:
      containers:
        - name: api
          image: myapp/api:v1.2.3      # always pin to digest or tag, never latest
          ports: [{ containerPort: 8080 }]
          resources:
            requests: { cpu: "100m", memory: "128Mi" }
            limits:   { cpu: "500m", memory: "512Mi" }
          livenessProbe:
            httpGet: { path: /health, port: 8080 }
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet: { path: /ready, port: 8080 }
            initialDelaySeconds: 5
            periodSeconds: 5
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef: { name: db-secret, key: url }
```

## Liveness vs Readiness Probes
- **Liveness**: is the process alive? (restart if fails) — check process health, not dependencies
- **Readiness**: is the pod ready to receive traffic? (remove from LB if fails) — check DB connectivity, cache, etc.
- Never fail liveness on external dependency — causes unnecessary restarts

## ConfigMap vs Secret
```yaml
# ConfigMap: non-sensitive config
apiVersion: v1
kind: ConfigMap
data:
  LOG_LEVEL: "info"
  PORT: "8080"

# Secret: sensitive values (base64 encoded, or use external-secrets-operator)
apiVersion: v1
kind: Secret
stringData:
  DATABASE_URL: "postgres://..."
```
Prefer `external-secrets-operator` + AWS Secrets Manager / Vault over in-cluster Secrets.

## HPA (Horizontal Pod Autoscaler)
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  scaleTargetRef: { kind: Deployment, name: api }
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
```

## Rules
- Always set resource `requests` AND `limits` — prevents noisy neighbor issues
- `minReplicas: 2` minimum — no single point of failure
- Namespaces per environment (`development`, `staging`, `production`)
- Rolling update strategy (default) — `maxSurge: 1, maxUnavailable: 0` for zero-downtime
- Never use `latest` image tag — use SHA digest or semantic version tag
- `PodDisruptionBudget` for critical services to prevent all pods being disrupted simultaneously
