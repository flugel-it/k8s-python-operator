IMG?=exampleoperatorpy:dev

dep:
	pip install -r requirements.txt

docker-build:
	docker build . -t ${IMG}

# Install CRDs and RBACs into a cluster
install:
	kubectl apply -f config/crds
	kubectl apply -f config/rbac

# Deploy controller in the configured Kubernetes cluster in ~/.kube/config
deploy: install
	kubectl apply -f config/default --namespace=system

# Remove controller in the configured Kubernetes cluster in ~/.kube/config
undeploy:
	kubectl delete -f config/default --namespace=system
	kubectl delete -f config/crds || true
	kubectl delete -f config/rbac || true
