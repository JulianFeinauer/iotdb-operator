# Simple IoTDB Operator for Kubernetes

Proof of Concept Implementation of an Operator to provide IoTDB Instances in Kubernetes.
An IoTDB Instance can be created by creating a CRD as the following example:

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

## Installation

To Install the Operator in a Cluster no Helm Chart is provided yet.
Thus one has to manually

* Install the CRD via `kubectl apply -f iotdb_crd.yaml`
* Adjust `operator.yaml` (edit namespace where the ServiceUser is created)
* Apply it via `kubectl apply -n <namespace> -f operator.yaml`

Then, you can test your installation by submitting the demo release via `kubectl apply -n <namespace> -f release.yaml`.