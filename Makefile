IMG?=exampleoperatorpy:dev

dep:
	pip install -r requirements.txt

docker-build:
	docker build . -t ${IMG}

crds:
	kubectl apply -f config/crds

namespace:
	kubectl apply -f config/namespace.yaml

permissions:
	kubectl apply -f config/rbac

run: crds
	python3 src/main.py --kubeconfig ~/.kube/config

install: namespace crds permissions

# Deploy controller in the configured Kubernetes cluster in ~/.kube/config
deploy: install
	kubectl apply -f config/default --namespace=immortalcontainers-operator

# Remove controller in the configured Kubernetes cluster in ~/.kube/config
undeploy:
	kubectl delete -f config/default --namespace=immortalcontainers-operator
	kubectl delete -f config/crds || true
	kubectl delete -f config/rbac || true
	kubectl delete -f config/namespace.yaml || true

