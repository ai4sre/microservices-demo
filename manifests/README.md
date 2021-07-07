# Kubernetes manifests

## How to Setup

### Setup GKE Cluster

1. Create GKE cluster.

```shell-session
$ export PROJECT_ID=$(gcloud config list --format 'value(core.project)') 
$ gcloud container clusters create sock-shop-01 \
	--region asia-northeast1-a \
	--release-channel regular \
	--cluster-version 1.19.10-gke.1700 \
	--image-type=cos \
	--machine-type e2-standard-2 \
	--workload-pool="${PROJECT_ID}.svc.id.goog" \
	--num-nodes 3 \
	--workload-metadata=GKE_METADATA
```

2. Create additional GKE node-pools.

```shell-session
$ gcloud container node-pools create control-pool \
	--cluster sock-shop-01 \
	--machine-type e2-medium \
	--image-type=cos \
	--num-nodes=1 \
	--workload-metadata=GKE_METADATA

$ gcloud container node-pools create analytics-pool \
	--cluster sock-shop-01 \
	--machine-type e2-small \
	--image-type=cos \
	--num-nodes=1 \
	--workload-metadata=GKE_METADATA
```

3. Setup for Workload Identity.

```shell-session
$ gcloud iam service-accounts create sock-shop-01
```

```shell-session
$ gcloud projects add-iam-policy-binding $PROJECT_ID --member serviceAccount:sock-shop-01@$PROJECT_IDwwwwwwwww.iam.gserviceaccount.com --role roles/storage.objectAdmin
```

```shell-session
$ gcloud iam service-accounts add-iam-policy-binding --role roles/iam.workloadIdentityUser --member "serviceAccount:$PROJECT_ID.svc.id.goog[litmus/argo-chaos]" sock-shop-01@$PROJECT_ID.iam.gserviceaccount.com
```

```shell-session
$ kubectl annotate serviceaccount --namespace litmus argo-chaos iam.gke.io/gcp-service-account=sock-shop-01@$PROJECT_ID.iam.gserviceaccount.com
```

4. Create GCS buckets (TBD)

### Deploy Sock Shop Application and Monitoring Stacks

```shell-session
$ helm plugin install https://github.com/databus23/helm-diff          
$ helmfile apply
$ kubectl apply -k .
```
