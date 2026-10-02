# Kubernetes patterns for container orchestration and production deployments.

## Deployment (stateless services)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api            # namespace comes from the kustomize overlay (<app>-dev, <app>-qa, …), never hardcoded
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
          image: registry/app/api@sha256:<digest>   # pin by DIGEST (overlay images block); never latest
          ports: [{ containerPort: 8080 }]
          resources:
            requests: { cpu: "100m", memory: "128Mi" }
            limits:   { cpu: "500m", memory: "512Mi" }
          livenessProbe:
            httpGet: { path: /healthz, port: 8080 }   # the runtime contract's paths (resiliency-patterns.md)
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet: { path: /readyz, port: 8080 }
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
metadata:
  name: api-config
data:
  LOG_LEVEL: "info"
  PORT: "8080"
---
# Secret: sensitive values. base64 is encoding, not encryption: never commit one with real values.
# Create it at deploy time (external-secrets-operator, or kustomize secretGenerator from a gitignored
# secrets.env); this is its shape only — the name and key the Deployment above reads.
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
type: Opaque
stringData:
  url: "postgres://..."
```
Prefer `external-secrets-operator` + AWS Secrets Manager / Vault over in-cluster Secrets.

## HPA (Horizontal Pod Autoscaler)
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: api }
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
```

## Rules
- Always set resource `requests` AND `limits` — prevents noisy neighbor issues
- `minReplicas: 2` minimum in staging/production — no single point of failure (dev/qa on the lab cluster may run 1)
- Namespaces per app per environment (`<app>-dev`, `<app>-qa`, …), set by kustomize overlays; RBAC per namespace
- Images declare a NUMERIC user (`USER 65532:65532`) so `runAsNonRoot: true` can be enforced
- Migrations/seeds as Jobs created from suspended CronJob templates (`kubectl create job --from=cronjob/…`),
  with a wait-for-db init container; promote environments by digest, not by rebuilding
- Rolling update strategy (default) — `maxSurge: 1, maxUnavailable: 0` for zero-downtime
- Never use `latest` image tag — use SHA digest or semantic version tag
- `PodDisruptionBudget` for critical services to prevent all pods being disrupted simultaneously

## Non-prod lab cluster
Local dev/qa environments (Lima + k3s, per-app namespaces, digest promotion, reset, rollback, and the
gotchas measured there): see `lima-k8s-lab.md` in this directory.

## Staging and production on Amazon EKS
`--target=staging|prod` runs the same kustomize base on EKS through a kustomize **Component**
(`deploy/k8s/components/eks`), so the base is never forked. The Component:
- swaps the in-cluster Postgres for RDS over TLS;
- takes `db-credentials` from AWS Secrets Manager with External Secrets Operator (same keys, same
  `db-access` policy);
- adds a PodDisruptionBudget, an HPA (the Deployment then sets no `replicas`), zone
  `topologySpreadConstraints`, requests/limits, a NetworkPolicy, and the EKS Auto Mode ALB IngressClass
  with the ACM certificate.

Images reach EKS only as digests promoted from qa (`crane copy` into ECR keeps the digest).
`deploylib.py eks-policy` refuses a render that breaks any of this.

Humans or CI deploy staging and prod; agents only author and validate the layer offline, and prod asks
for a confirmation every time. Full model, choices and sources: `eks.md` in this directory.

> Config blocks checked 2026-09-30 (`bash tests/archetype-compile/config-packs/run.sh --live`): 3 YAML blocks parsed (duplicate keys fail), kubeconform -strict (Kubernetes 1.37.1 schemas).
