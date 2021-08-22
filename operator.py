import os

import kopf
import kubernetes as kubernetes
import yaml
from kubernetes.client import V1StatefulSet


@kopf.on.create('iotdbreleases')
def create_fn(spec, name, namespace, logger, **kwargs):
    image = spec.get('image')
    if not image:
        raise kopf.PermanentError(f"Image must be set. Got {image!r}.")
    adminPassword = spec.get('adminPassword')
    if not adminPassword:
        raise kopf.PermanentError(f"adminPassword must be set!")

    api = kubernetes.client.CoreV1Api()
    apps_api = kubernetes.client.AppsV1Api()
    batch_api = kubernetes.client.BatchV1Api()

    # Statefulset
    context = {"name": name, "image": image, "adminPassword": adminPassword}
    data = get_ressource('templates/statefulset.yaml', **context)
    kopf.adopt(data, nested="spec.template")
    statefulset: V1StatefulSet = apps_api.create_namespaced_stateful_set(namespace=namespace, body=data)
    logger.info(f"Statefulset child is created: {statefulset}")

    # Service
    data = get_ressource('templates/service.yaml', **context)
    kopf.adopt(data, nested="spec.template")
    servcice = api.create_namespaced_service(namespace=namespace, body=data)
    logger.info(f"Service child is created: {servcice}")

    # Headless Service
    data = get_ressource('templates/headless-service.yaml', **context)
    kopf.adopt(data, nested="spec.template")
    headless_service = api.create_namespaced_service(namespace=namespace, body=data)
    logger.info(f"Headless Service child is created: {headless_service}")

    # Job
    data = get_ressource('templates/job.yaml', **context)
    kopf.adopt(data, nested="spec.template")
    job = batch_api.create_namespaced_job(namespace=namespace, body=data)
    logger.info(f"Job child is created: {job}")

    return {"statefullset": statefulset.metadata.name,
            "service": servcice.metadata.name,
            "headless-service": headless_service.metadata.name,
            "job": job.metadata.name
            }


def get_ressource(filename, **kwargs):
    path = os.path.join(os.path.dirname(__file__), filename)
    tmpl = open(path, 'rt').read()
    text = tmpl.format(**kwargs)
    data = yaml.safe_load(text)
    return data
