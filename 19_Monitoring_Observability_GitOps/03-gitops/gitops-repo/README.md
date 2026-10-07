# gitops-demo

Desired state for the `podinfo` app in two environments. Argo CD watches this repo and makes the cluster match it.

```
apps/                      Argo CD Applications (the root app points here: app-of-apps)
podinfo/base/              Deployment + Service shared by every environment
podinfo/overlays/dev/      1 replica,  dev message
podinfo/overlays/prod/     2 replicas, prod message
```

Change the cluster by changing this repo: commit, push, Argo CD syncs.
