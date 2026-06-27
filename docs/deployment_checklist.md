# Production Deployment & Disaster Recovery Checklist

This checklist outlines the operations runbooks for deploying, maintaining, and recovering the **DOCSCOPE AI** platform in production environments.

---

## 1. Pre-Deployment Configuration (Pre-Flight)

Before deploying to the production Kubernetes cluster, verify the following prerequisites:

### [ ] Infrastructure Configuration
- [ ] Ensure Kubernetes cluster version is v1.26 or higher.
- [ ] Install **NGINX Ingress Controller** in the cluster.
- [ ] Install **KEDA (Kubernetes Event-driven Autoscaling)** for Celery queue autoscaling:
  ```bash
  helm repo add kedacore https://kedacore.github.io/charts
  helm repo update
  helm install keda kedacore/keda --namespace keda --create-namespace
  ```
- [ ] Configure the **NVIDIA Device Plugin** on the GPU node pool so nodes advertise GPU resources:
  ```bash
  kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.0/nvidia-device-plugin.yml
  ```

### [ ] External API & Services Credentials
- [ ] Verify Gemini API Key quota and model availability (`gemini-1.5-flash`).
- [ ] Procure SSL Certificates for production domains.
- [ ] Create S3 storage bucket (`docscope-storage`) and obtain access/secret keys.

---

## 2. Production Deployment Runbook

Deploy the application using the Helm charts provided in the `k8s/helm/docscope` directory.

### [ ] Step 1: Update Helm Values
Open [values.yaml](file:///d:/docscope/k8s/helm/docscope/values.yaml) and update:
- `global.environment` set to `production`.
- `config.geminiApiKey` set to your live production key.
- `config.dbPassword` set to a strong password.
- `config.s3Endpoint` and credentials set to production S3.

### [ ] Step 2: Test Chart Rendering
Run a dry run template generation to check for errors:
```bash
helm template docscope k8s/helm/docscope/
```

### [ ] Step 3: Deploy Helm Chart
Install/upgrade the chart in the `docscope-prod` namespace:
```bash
helm upgrade --install docscope k8s/helm/docscope/ \
  --namespace docscope-prod \
  --create-namespace \
  --values k8s/helm/docscope/values.yaml
```

### [ ] Step 4: Run Alembic Database Migrations
Run Alembic migrations to construct the database schema and initialize partitioned tables:
```bash
kubectl exec -it deployment/docscope-api -n docscope-prod -- alembic upgrade head
```

### [ ] Step 5: Verify Deployments & HPA Scalers
Check that all deployments are online and KEDA scaled object is registered:
```bash
kubectl get pods -n docscope-prod
kubectl get scaledobject -n docscope-prod
```

---

## 3. Disaster Recovery & Backup/Restore Runbook

To guarantee data integrity and platform reliability, run database backups and S3 synchronization tasks regularly.

### [ ] Backup Database (PostgreSQL)
Because `audit_logs` and `usage_metrics` tables are range-partitioned:
- Use `pg_dump` with custom format (`-Fc`) which captures the partition hierarchies and schema relationships perfectly.
- To perform a backup run:
  ```bash
  kubectl exec -it deployment/docscope-postgres -n docscope-prod -- \
    pg_dump -U postgres -d docscope -Fc -f /tmp/docscope_backup.dump
  
  # Download dump locally
  kubectl cp docscope-prod/$(kubectl get pods -l app=postgres -n docscope-prod -o jsonpath='{.items[0].metadata.name}'):/tmp/docscope_backup.dump ./docscope_backup.dump
  ```

### [ ] Restore Database (PostgreSQL)
To restore a backup dump into a clean instance:
1. Re-initialize the schema using `pg_restore` (it handles range-partition metadata automatically):
   ```bash
   kubectl cp ./docscope_backup.dump docscope-prod/$(kubectl get pods -l app=postgres -n docscope-prod -o jsonpath='{.items[0].metadata.name}'):/tmp/docscope_backup.dump
   
   kubectl exec -it deployment/docscope-postgres -n docscope-prod -- \
     pg_restore -U postgres -d docscope -c --clean --if-exists /tmp/docscope_backup.dump
   ```
2. Re-apply the Alembic migration command if some new schema changes are missing.

### [ ] Storage Sync (S3/MinIO)
- Sync original uploaded documents and rendered page PNGs:
  ```bash
  # Backup bucket files
  aws s3 sync s3://docscope-storage ./s3_backup/
  
  # Restore bucket files
  aws s3 sync ./s3_backup/ s3://docscope-storage
  ```

### [ ] Qdrant Vector Data Recovery
- Qdrant keeps all indices in `/qdrant/storage`.
- In case of collection corruption, Qdrant snapshots can be created and restored:
  ```bash
  # Create snapshot
  curl -X POST http://docscope-qdrant:6333/collections/pages/snapshots
  
  # Download and store the snapshot file (.snapshot)
  ```
- To restore a snapshot:
  ```bash
  curl -X POST http://docscope-qdrant:6333/collections/pages/snapshots/recover \
    -H 'Content-Type: application/json' \
    -d '{"location": "http://backup-server/pages.snapshot"}'
  ```
