#!/usr/bin/env bash
# Install Argo Workflows on a local kind cluster and run the pipeline DAG.
set -euo pipefail

if ! command -v kind >/dev/null 2>&1; then
  curl -fsSL -o /tmp/kind "https://kind.sigs.k8s.io/dl/v0.29.0/kind-linux-amd64"
  chmod +x /tmp/kind
  sudo mv /tmp/kind /usr/local/bin/kind
fi
if ! command -v helm >/dev/null 2>&1; then
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

docker build -t living-cost-squeeze:local .
kind delete cluster --name squeeze >/dev/null 2>&1 || true
kind create cluster --name squeeze
kind load docker-image living-cost-squeeze:local --name squeeze
kubectl apply -f argo/rbac.yaml
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
helm upgrade --install argo-workflows argo/argo-workflows \
  --namespace argo --create-namespace \
  -f argo/values.yaml \
  --wait --timeout 8m
kubectl delete workflow living-cost-squeeze --ignore-not-found
kubectl create -f argo/workflow.yaml
kubectl wait --for=condition=Completed workflow/living-cost-squeeze --timeout=900s
kubectl logs -l workflows.argoproj.io/workflow=living-cost-squeeze --all-containers --tail=-1 | tee /tmp/argo-squeeze.log
grep -q "EMPLOYEE_LCI_YOY_2026Q3=5.1" /tmp/argo-squeeze.log
echo "Argo workflow published the September 2026 working-household result."
