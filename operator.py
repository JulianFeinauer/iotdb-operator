import os

import kopf
import kubernetes as kubernetes
import yaml
from kopf import Spec, Status
from kubernetes.client import V1StatefulSet


#
# api = kubernetes.client.CoreV1Api()
# apps_api = kubernetes.client.AppsV1Api()
# batch_api = kubernetes.client.BatchV1Api()
# custom_api = kubernetes.client.CustomObjectsApi()
# crd_api = kubernetes.client.ApiextensionsV1Api()

def patch_status(logger, namespace, name, key, value):
    logger.info("Patching status...")

    custom_api = kubernetes.client.CustomObjectsApi()

    # Patch configmap in
    data = {
        "status": {
            key: value
        }
    }

    custom_api.patch_namespaced_custom_object(group="jfeinauer.dev", version="v1", namespace=namespace,
                                              plural="iotdbreleases", name=name, body=data)


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
    data = get_ressource('templates/job.yaml', **context)

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
    data = get_ressource('templates/headless-service.yaml', **context)

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
    data = get_ressource('templates/service.yaml', **context)

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
    data = get_ressource('templates/statefulset.yaml', **context)

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
    data = get_ressource('templates/configmap.yaml', **context)

    # Add Values if any are set
    if not spec.get("engine-config", None):
        logger.info("No Engine Configs found, skipping...")
    else:
        # Load Properties
        properties = data["data"]["iotdb-engine.properties"]

        for k,v in spec["engine-config"].items():
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
