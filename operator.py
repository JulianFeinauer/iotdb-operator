import os

import kopf
import kubernetes as kubernetes
import yaml
from kopf import Spec, Status
from kubernetes.client import V1StatefulSet, V1ConfigMap, CoreV1Api, V1Service, V1Job


#
# api = kubernetes.client.CoreV1Api()
# apps_api = kubernetes.client.AppsV1Api()
# batch_api = kubernetes.client.BatchV1Api()
# custom_api = kubernetes.client.CustomObjectsApi()
# crd_api = kubernetes.client.ApiextensionsV1Api()

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

    logger.info(f"Creating Cluster {name} with {seed_node_count} seed-nodes")

    context = {
        "name": name,
        "admin_password": admin_password,
        "seed_node_count": seed_node_count,
        "version": version,
        "image": image
    }
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

class Handler(object):
    api_class = None
    object = None
    return_class = None

    def create_or_patch(self, logger, namespace, body) -> return_class:
        api = self.__class__.api_class()
        try:
            read_method = getattr(api, f"read_namespaced_{self.__class__.object}")
            read_method(namespace=namespace, name=body["metadata"]["name"])
            # Delete it?!
            # Patch it
            logger.info(f"Patchin existing {self.__class__.object}")
            patch_method = getattr(api, f"patch_namespaced_{self.__class__.object}")
            config = patch_method(namespace=namespace, name=body["metadata"]["name"], body=body)
        except:
            logger.info(f"Creating {self.__class__.object}")
            create_method = getattr(api, f"create_namespaced_{self.__class__.object}")
            config = create_method(namespace=namespace, body=body)
        return config


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


# def create_or_patch_configmap(logger, namespace, body) -> V1ConfigMap:
#     api = kubernetes.client.CoreV1Api()
#     try:
#         api.st(namespace=namespace, name=body["metadata"]["name"])
#         # Patch it
#         config: V1StatefulSet = api.patch_namespaced_config_map(namespace=namespace, name=body["metadata"]["name"],
#                                                                 body=body)
#     except:
#         logger.info(f"Creating...")
#         config: V1StatefulSet = api.create_namespaced_config_map(namespace=namespace, body=body)
#     return config
#
#
# def create_or_patch_configmap(logger, namespace, body) -> V1StatefulSet:
#     api = kubernetes.client.CoreV1Api()
#     try:
#         api.read_namespaced_config_map(namespace=namespace, name=body["metadata"]["name"])
#         # Patch it
#         config: V1StatefulSet = api.patch_namespaced_config_map(namespace=namespace, name=body["metadata"]["name"],
#                                                                 body=body)
#     except:
#         logger.info(f"Creating...")
#         config: V1StatefulSet = api.create_namespaced_config_map(namespace=namespace, body=body)
#     return config
