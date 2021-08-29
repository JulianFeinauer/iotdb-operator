import os
from typing import Optional

import os
from typing import Optional

import kopf
import kubernetes as kubernetes
import yaml
from kopf import Spec, Status
from kubernetes.client import V1StatefulSet, V1ConfigMap, V1Service, V1Job


# TODO Enable this together with Admission Control (see Validaation below)
# @kopf.on.startup()
# def configure(settings: kopf.OperatorSettings, **_):
#     settings.admission.server = kopf.WebhookAutoTunnel()
#     settings.admission.managed = 'jfeinauer.dev'

def patch_status(logger, namespace, name, key, value, group="jfeinauer.dev", version="v1", plural="iotdbreleases"):
    logger.info("Patching status...")

    custom_api = kubernetes.client.CustomObjectsApi()

    # Patch configmap in
    data = {
        "status": {
            key: value
        }
    }

    custom_api.patch_namespaced_custom_object(group=group, version=version, namespace=namespace,
                                              plural=plural, name=name, body=data)


@kopf.on.resume('iotdbreleases')
@kopf.on.create('iotdbreleases')
def create_or_resume_fn(spec: Spec, name, namespace, logger, status: Status, **kwargs):
    logger.info(f"Resuming...{name}")
    context = get_context(name, spec)

    api = kubernetes.client.CoreV1Api()

    logger.info(f"Current Status: {status}")

    if not status.get("configmap", None):
        # Create the Map
        config = create_configmap_if_not_exists(spec, context, logger, namespace)

        # Patch configmap in
        patch_status(logger, namespace, name, "configmap", config.metadata.name)

    if not status.get("statefullset", None):
        logger.info("Statefullset not found")
        statefullset = create_statefulset_if_not_exists(context, logger, namespace)

        # Patch configmap in
        patch_status(logger, namespace, name, "statefullset", statefullset.metadata.name)
    else:
        logger.info("Statefullset found")

    if not status.get("service", None):
        logger.info("service not found")
        service = create_service_if_not_exists(context, logger, namespace)

        # Patch configmap in
        patch_status(logger, namespace, name, "service", service.metadata.name)
    else:
        logger.info("Service found")

    if not status.get("headless-service", None):
        logger.info("service not found")
        service = create_headless_service_if_not_exists(context, logger, namespace)

        # Patch configmap in
        patch_status(logger, namespace, name, "headless-service", service.metadata.name)
    else:
        logger.info("Service found")

    if not status.get("job", None):
        logger.info("job not found")
        job = create_job_if_not_exists(context, logger, namespace)

        # Patch configmap in
        patch_status(logger, namespace, name, "job", job.metadata.name)
    else:
        logger.info("Job found")


def create_job_if_not_exists(context, logger, namespace):
    batch_api = kubernetes.client.BatchV1Api()
    data = get_ressource('templates/node/job.yaml', **context)

    try:
        job = batch_api.read_namespaced_job(namespace=namespace, name=data["metadata"]["name"])
        logger.info("Job with the name already exists, returing it...")
    except:
        kopf.adopt(data, nested="spec.template")
        job = batch_api.create_namespaced_job(namespace=namespace, body=data)
        logger.info(f"Job child is created")
    return job


def create_headless_service_if_not_exists(context, logger, namespace):
    api = kubernetes.client.CoreV1Api()
    data = get_ressource('templates/node/headless-service.yaml', **context)

    try:
        headless_service = api.read_namespaced_service(namespace=namespace, name=data["metadata"]["name"])
        logger.info("Headless Service with the name already exists, returing it...")
    except:
        kopf.adopt(data, nested="spec.template")
        headless_service = api.create_namespaced_service(namespace=namespace, body=data)
        logger.info(f"Headless Service child is created")
    return headless_service


def create_service_if_not_exists(context, logger, namespace):
    api = kubernetes.client.CoreV1Api()
    data = get_ressource('templates/node/service.yaml', **context)

    try:
        service = api.read_namespaced_service(namespace=namespace, name=data["metadata"]["name"])
        logger.info("Service with the name already exists, returing it...")
    except:
        kopf.adopt(data, nested="spec.template")
        service = api.create_namespaced_service(namespace=namespace, body=data)
        logger.info(f"Service child is created")
    return service


def create_statefulset_if_not_exists(context, logger, namespace):
    apps_api = kubernetes.client.AppsV1Api()
    data = get_ressource('templates/node/statefulset.yaml', **context)

    # Check if ressource exists
    try:
        statefulset: V1StatefulSet = apps_api.read_namespaced_stateful_set(namespace=namespace,
                                                                           name=data["metadata"]["name"])
        logger.info("Statefulset with the name already exists, returing it...")
        return statefulset
    except:
        kopf.adopt(data, nested="spec.template")
        statefulset: V1StatefulSet = apps_api.create_namespaced_stateful_set(namespace=namespace, body=data)
        logger.info(f"Statefulset child is created")
        return statefulset


def get_context(name, spec):
    image = spec.get('image')
    if not image:
        raise kopf.PermanentError(f"Image must be set. Got {image!r}.")
    adminPassword = spec.get('adminPassword')
    if not adminPassword:
        raise kopf.PermanentError(f"adminPassword must be set!")
    context = {"name": name, "image": image, "adminPassword": adminPassword}
    return context


def create_configmap_if_not_exists(spec, context, logger, namespace):
    api = kubernetes.client.CoreV1Api()
    data = get_ressource('templates/node/configmap.yaml', **context)

    # Add Values if any are set
    if not spec.get("engine-config", None):
        logger.info("No Engine Configs found, skipping...")
    else:
        # Load Properties
        properties = data["data"]["iotdb-engine.properties"]

        for k, v in spec["engine-config"].items():
            logger.info(f"Config {k} -> {v}")

            # Iterate all Lines
            for line in iter(properties.splitlines()):
                if line.startswith(k):
                    logger.info(f"Found line: {line}, patching....")
                    properties = properties.replace(line, f"{k}={v}")
                    break
            else:
                logger.warn(f"Did not find line for property {k}!")

        data["data"]["iotdb-engine.properties"] = properties

    # Check if ressource exists
    try:
        config: V1StatefulSet = api.read_namespaced_config_map(namespace=namespace, name=data["metadata"]["name"])
        logger.info("Config with the name already exists, returing it...")
        return config
    except:
        kopf.adopt(data)
        config: V1StatefulSet = api.create_namespaced_config_map(namespace=namespace, body=data)
        logger.info(f"Config child is created")
        return config


def get_ressource(filename, **kwargs):
    path = os.path.join(os.path.dirname(__file__), filename)
    tmpl = open(path, 'rt').read()
    text = tmpl.format(**kwargs)
    data = yaml.safe_load(text)
    return data


@kopf.on.event("statefulset")
def statefulset_change(event, logger, status, spec, **_):
    """
    Reports changes in the statefulset ("seed pods")
    """
    owners = event.get('object').get('metadata').get('ownerReferences')

    if owners:
        owner = owners[0]
        kind = owner.get('kind')
        name = owner.get('name')
        namespace = event.get('object').get('metadata').get('namespace')
        if kind == "IoTDBCluster":
            logger.info(f"Expected replicas {spec.get('replicas')}, currently have {status.get('readyReplicas')}")
            # Now we can patch the owner
            patch_status(logger, namespace, name, "seedReplicasTotal", value=spec.get('replicas'), plural="iotdbclusters")
            patch_status(logger, namespace, name, "seedReplicasReady", value=status.get('readyReplicas'), plural="iotdbclusters")

            if int(spec.get('replicas')) == int(status.get('readyReplicas')):
                patch_status(logger, namespace, name, "seed_pods_ready", value=True, plural="iotdbclusters")
            else:
                patch_status(logger, namespace, name, "seed_replicas_ready", value=False, plural="iotdbclusters")


@kopf.on.event("service")
def service_change(event, logger, status, spec, **_):
    metadata = event.get('object').get('metadata')
    owners = metadata.get('ownerReferences')

    if owners:
        owner = owners[0]
        kind = owner.get('kind')
        name = owner.get('name')
        namespace = metadata.get('namespace')

        if kind == "IoTDBCluster":
            if spec.get('type') == "LoadBalancer":
                logger.info(f"Service is {metadata.get('name')}, status is {status}")
            else:
                logger.info(f"Service {metadata.get('name')} is headless, skipping...")
                return

            # status:
            #     loadBalancer:
            #     ingress:
            #     - ip: 85.215.241.207
            external_ip = None
            try:
                external_ip = status.get('loadBalancer').get('ingress')[0].get('ip')
            except:
                pass

            logger.info(f"Setting external_ip: {external_ip}")
            # Patch the status
            patch_status(logger, namespace, name, "external_ip", value=external_ip, plural="iotdbclusters")


@kopf.on.event("job")
def job_change(event, logger, status, spec, **_):
    metadata = event.get('object').get('metadata')
    owners = metadata.get('ownerReferences')

    if owners:
        owner = owners[0]
        kind = owner.get('kind')
        name = owner.get('name')
        namespace = metadata.get('namespace')

        if kind == "IoTDBCluster":
            succeeded_count = status.get('succeeded')
            if not succeeded_count or succeeded_count < 1:
                patch_status(logger, namespace, name, "initialization_done", value=False, plural="iotdbclusters")
            else:
                patch_status(logger, namespace, name, "initialization_done", value=True, plural="iotdbclusters")

@kopf.on.resume('iotdbclusters')
@kopf.on.create("iotdbclusters")
def create_or_resume(spec: Spec, name, namespace, logger, status: Status, **kwargs):
    logger.info(f"Operator is active, checking object {name}")

    # Create configmaps
    version = spec.get('version')
    if not version:
        raise kopf.PermanentError(f"version must be set!.")

    if version == "0.12.2":
        image = "jfeinauer/apache-iotdb-cluster:0.12.2"
    else:
        raise kopf.PermanentError(f"Version {version} currently not supported!")

    admin_password = spec.get('adminPassword')

    seed_node_count = spec.get('seedNodes')
    if not seed_node_count or seed_node_count < 2:
        raise kopf.PermanentError(f"seedNodes must be set and greater than or equal to 2!.")

    replicas = spec.get("replicas")
    if not replicas or replicas != seed_node_count:
        raise kopf.PermanentError(f"replicas must be specified and currently be equal to seed nodes")

    logger.info(f"Creating Cluster {name} with {seed_node_count} seed-nodes")

    context = {
        "name": name,
        "admin_password": admin_password,
        "seed_node_count": seed_node_count,
        "version": version,
        "image": image
    }
    # Add Seed Nodes
    context["seed_nodes"] = ",".join(
        [f"{name}-seeds-{i}.{name}.{namespace}.svc.cluster.local:9003" for i in range(0, seed_node_count)]
    )

    if not status.get("seed_node_configmap"):
        data = get_ressource('templates/cluster/configmap.yaml', **context)
        kopf.adopt(data)

        logger.info(f"Prepared Configmap created")

        config = ConfigMapHandler().create_or_patch(logger, namespace, data)

        # Update status
        patch_status(logger, namespace, name, "seed_node_configmap", config.metadata.name, plural="iotdbclusters")

    # Create the Statefulset
    if not status.get("seed_node_statefulset"):
        data = get_ressource('templates/cluster/statefulset.yaml', **context)
        kopf.adopt(data)

        sset = StatefulSetHandler().create_or_patch(logger, namespace, data)

        # Update status
        patch_status(logger, namespace, name, "seed_node_statefulset", sset.metadata.name, plural="iotdbclusters")

    # Create Headless Service
    if not status.get("seed_node_hservice"):
        data = get_ressource('templates/cluster/headless-service.yaml', **context)
        kopf.adopt(data)

        hservice = ServiceHandler().create_or_patch(logger, namespace, data)

        # Update status
        patch_status(logger, namespace, name, "seed_node_hservice", hservice.metadata.name, plural="iotdbclusters")

    # Create Regular Service
    if not status.get("seed_node_service"):
        data = get_ressource('templates/cluster/service.yaml', **context)
        kopf.adopt(data)

        hservice = ServiceHandler().create_or_patch(logger, namespace, data)

        # Update status
        patch_status(logger, namespace, name, "seed_node_service", hservice.metadata.name, plural="iotdbclusters")

    if admin_password:
        if not status.get("seed_node_init_job"):
            data = get_ressource('templates/cluster/job.yaml', **context)
            kopf.adopt(data)

            hservice = JobHandler().create_or_patch(logger, namespace, data)

            # Update status
            patch_status(logger, namespace, name, "seed_node_init_job", hservice.metadata.name, plural="iotdbclusters")


# @kopf.on.validate("iotdbclusters")
# def validate(spec, **_):
#     """
#     TODO Add this
#     :param spec:
#     :param _:
#     :return:
#     """
#     logging.info("Validating...")
#     logging.info(f"Spec: {spec}")
#     for k,v in _.items():
#         logging.info(f"Ohter: {k} -> {v}")
#     # Get the object (if it exists)
#     handler = CustomObjectHandler()


class Handler(object):
    read_verb = "read"
    api_class = None
    object = None
    return_class = None

    def __init__(self) -> None:
        self.api = self.__class__.api_class()
        self.read_method = getattr(self.api, f"{self.__class__.read_verb}_namespaced_{self.__class__.object}")
        self.patch_method = getattr(self.api, f"patch_namespaced_{self.__class__.object}")
        self.create_method = getattr(self.api, f"create_namespaced_{self.__class__.object}")

    def create_or_patch(self, logger, namespace, body, **kwargs) -> return_class:
        try:
            self.read_method(namespace=namespace, name=body["metadata"]["name"], **kwargs)
            # Delete it?!
            # Patch it
            logger.info(f"Patchin existing {self.__class__.object}")
            config = self.patch_method(namespace=namespace, name=body["metadata"]["name"], body=body, **kwargs)
        except:
            logger.info(f"Creating {self.__class__.object}")
            config = self.create_method(namespace=namespace, body=body, **kwargs)
        return config

    def get(self, namespace, name) -> Optional[return_class]:
        try:
            return self.read_method(namespace=namespace, name=name)
        except:
            return None

class ConfigMapHandler(Handler):
    api_class = kubernetes.client.CoreV1Api
    object = "config_map"
    return_class = V1ConfigMap


class StatefulSetHandler(Handler):
    api_class = kubernetes.client.AppsV1Api
    object = "stateful_set"
    return_class = V1StatefulSet

class ServiceHandler(Handler):
    api_class = kubernetes.client.CoreV1Api
    object = "service"
    return_class = V1Service


class JobHandler(Handler):
    api_class = kubernetes.client.BatchV1Api
    object = "job"
    return_class = V1Job


class CustomObjectHandler(Handler):
    read_verb = "get"
    api_class = kubernetes.client.CustomObjectsApi
    object = "custom_object"
    return_class = object