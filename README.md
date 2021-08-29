# Simple IoTDB Operator for Kubernetes

Proof of Concept Implementation of an Operator to provide IoTDB Instances in Kubernetes.

## Create a Single Node Instance

A single-node IoTDB Instance can be created by creating a CRD as the following example:

```
apiVersion: jfeinauer.dev/v1
kind: IoTDBRelease
metadata:
  name: my-new-itodb
  labels:
    creator: julian
spec:
  adminPassword: "Hallo"
  image: "apache/iotdb:0.11.2"
  # Here you can override any entry from IoTDBs iotdb-engine.properties file
  engine-config:
    enable_wal: "false"
```

The fields `adminPassword` and `image` are required and under `engine-config` one can optionally override every property from the `iotdb-engine.properties` file, see [Configuration](http://iotdb.apache.org/UserGuide/V0.10.x/Server/Config%20Manual.html).

## Create a Cluster

To create a HA Cluster (based on IoTDBs Cluster Support, see https://iotdb.apache.org/UserGuide/Master/Cluster/Cluster-Setup.html), just create a namespaced ressource as follows:

```
apiVersion: jfeinauer.dev/v1
kind: IoTDBCluster
metadata:
  name: my-cluster
spec:
  adminPassword: "Hallo"
  version: "0.12.2"  ## Only supported Version at the moment
  seedNodes: 2
  replicas: 2  ## Currently has to be equal to replicas
```

## Installation

To Install the Operator in a Cluster no Helm Chart is provided yet.
Thus one has to manually

* Install the CRDs via `kubectl apply -f iotdb_crd.yaml` and `kubectl apply -f iotdb_cluster_crd.yaml`
* Adjust `operator.yaml` (edit namespace where the ServiceUser is created)
* Apply it via `kubectl apply -n <namespace> -f operator.yaml`

Then, you can test your installation by submitting the demo release via `kubectl apply -n <namespace> -f release.yaml` or `kubectl apply -n <namespace> -f cluster_release.yaml`.

## Next steps

- [x] Add all necessary information from child containers (external ip, port, password, ...) to `status` when they are ready
- [ ] Add Validation for changes on image (and probably also admin pw?)
- [ ] Add Patching behavior on config entry Changes
- [ ] Allow support for tcp port sharing (with nginx-ingress)
- [x] Allow Support for Cluster