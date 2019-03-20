# exampleoperatorpy

This repository implements an example Kubernetes operator in Python 3, called "ImmortalContainers". This operator enables the user to define, using custom resources, containers that must run and if terminated must be restarted.

The following diagram shows the main components of this operator controller:

![components diagram](https://github.com/flugel-it/k8s-python-operator/raw/master/docs/components_diagram.png "Components diagram")

## Venv and project dependencies

To create a virtual env and install the project dependencies follow these steps:

```bash
python3 -m venv venv
. ./venv/bin/activate
make dep
```

## Install CRD and RBAC permissions

To install CRDs and RBAC configurations to your currently set cluster use:

```bash
make install
```

## Running the operator outside the cluster

```bash
. ./venv/bin/activate
python src/main.py --kubeconfig ~/.kube/config
```

## Running inside the cluster

You must first generate the image using `make docker-build` and push it to your repo.

If using **minikube** follow these steps:

```bash
eval $(minikube docker-env)
make docker-build
```

Then create the `system` namespace

```bash
kubectl apply -f config/namespace.yaml
```

And then run `make deploy`.

After this you should check that everything is running, ex:

```bash
$ kubectl get pods --namespace system                     
NAME                                          READY   STATUS    RESTARTS   AGE
exampleoperatorpy-controller-7cb7f99658-97zjs   1/1     Running   0          24m

$ kubectl logs exampleoperatorpy-controller-7cb7f99658-97zjs --namespace=system

INFO:controller:Controller starting
```

## Using the operator

Once the operator is running you can create immortal containers using a custom resource like this one:

```yaml
apiVersion: immortalcontainer.flugel.it/v1alpha1
kind: ImmortalContainer
metadata:
  name: example-immortal-container
spec:
  image: nginx:latest
```

Run `kubectl apply -f config/example-use.yaml` to try it.

Then run `kubectl get pods` and check the pod is created. If you kill the pod it will be recreated.

## Remove the operator

To remove the operator, CDR and RBAC use `make undeploy`

Pods created by the operator will not be deleted, but will not be restarted if deleted later.