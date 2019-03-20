import logging
import queue
import threading

from kubernetes.client.rest import ApiException
from kubernetes.client import models
import copy

logger = logging.getLogger('controller')


class Controller(threading.Thread):
    """Reconcile current and desired state by listening for events and making
       calls to Kubernetes API.
    """

    def __init__(self, pods_watcher, immortalcontainers_watcher, corev1api,
                 customsapi, custom_group, custom_version, custom_plural,
                 custom_kind, workqueue_size=10):
        """Initializes the controller.

        :param pods_watcher: Watcher for pods events.
        :param immortalcontainers_watcher: Watcher for immortalcontainers custom
                                           resource events.
        :param corev1api: kubernetes.client.CoreV1Api()
        :param customsapi: kubernetes.client.CustomObjectsApi()
        :param custom_group: The custom resource's group name
        :param custom_version: The custom resource's version
        :param custom_plural: The custom resource's plural name.
        :param custom_kind: The custom resource's kind name.
        :param workqueue_size: queue size for resources that must be processed.
        """
        super().__init__()
        # `workqueue` contains namespace/name of immortalcontainers whose status
        # must be reconciled
        self.workqueue = queue.Queue(workqueue_size)
        self.pods_watcher = pods_watcher
        self.immortalcontainers_watcher = immortalcontainers_watcher
        self.corev1api = corev1api
        self.customsapi = customsapi
        self.custom_group = custom_group
        self.custom_version = custom_version
        self.custom_plural = custom_plural
        self.custom_kind = custom_kind
        self.pods_watcher.add_handler(self._handle_pod_event)
        self.immortalcontainers_watcher.add_handler(
            self._handle_immortalcontainer_event)

    def _handle_pod_event(self, event):
        """Handle an event from the pods watcher putting the pod's corresponding
           immortalcontroller in the `workqueue`. """
        obj = event['object']
        owner_name = ""
        if obj.metadata.owner_references is not None:
            for owner_ref in obj.metadata.owner_references:
                if owner_ref.api_version == self.custom_group+"/"+self.custom_version and \
                        owner_ref.kind == self.custom_kind:
                    owner_name = owner_ref.name
        if owner_name != "":
            self._queue_work(obj.metadata.namespace+"/"+owner_name)

    def _handle_immortalcontainer_event(self, event):
        """Handle an event from the immortalcontainers watcher putting the
           object name in the `workqueue`."""
        self._queue_work(event['object']['metadata']['namespace'] +
                         "/"+event['object']['metadata']['name'])

    def _queue_work(self, object_key):
        """Add a object name to the work queue."""
        if len(object_key.split("/")) != 2:
            logger.error("Invalid object key: {:s}".format(object_key))
            return
        self.workqueue.put(object_key)

    def run(self):
        """Dequeue and process objects from the `workqueue`. This method
           should not be called directly, but using `start()"""
        self.running = True
        logger.info('Controller starting')
        while self.running:
            e = self.workqueue.get()
            if not self.running:
                self.workqueue.task_done()
                break
            try:
                self._reconcile_state(e)
                self.workqueue.task_done()
            except Exception as ex:
                logger.error(
                    "Error _reconcile state {:s}".format(e),
                    exc_info=True)

    def stop(self):
        """Stops this controller thread"""
        self.running = False
        self.workqueue.put(None)

    def _reconcile_state(self, object_key):
        """Make changes to go from current state to desired state and updates
           object status."""
        logger.info("Reconcile state: {:s}".format(object_key))
        ns, name = object_key.split("/")

        # Get object if it exists
        try:
            immortalcontainer = self.customsapi.get_namespaced_custom_object(
                self.custom_group, self.custom_version, ns, self.custom_plural, name)
        except ApiException as e:
            if e.status == 404:
                logger.info(
                    "Element {:s} in workqueue no longer exist".format(object_key))
                return
            raise e

        # Create pod definition
        pod_definition = self._new_pod(immortalcontainer)
        pod = None
        try:
            pod = self.corev1api.read_namespaced_pod(
                pod_definition.metadata.name, ns)
        except ApiException as e:
            if e.status != 404:
                logger.info("Error retrieving pod {:s} for immortalcontainer {:s}".format(
                    pod_definition.metadata.name, object_key))
                raise e

        if pod is None:
            # If no pod exists create one
            pod = self.corev1api.create_namespaced_pod(ns, pod_definition)
            # update status
            self._update_status(immortalcontainer, pod)

    def _update_status(self, immortalcontainer, pod):
        """Updates an ImmortalContainer status"""
        new_status = self._calculate_status(immortalcontainer, pod)
        try:
            self.customsapi.patch_namespaced_custom_object_status(
                self.custom_group, self.custom_version,
                immortalcontainer['metadata']['namespace'],
                self.custom_plural, immortalcontainer['metadata']['name'],
                new_status
            )
        except Exception as e:
            logger.error("Error updating status for ImmortalContainer {:s}/{:s}".format(
                immortalcontainer['metadata']['namespace'], immortalcontainer['metadata']['name']))

    def _calculate_status(self, immortalcontainer, pod):
        """Calculates what the status of an ImmortalContainer should be """
        new_status = copy.deepcopy(immortalcontainer)
        if 'status' in immortalcontainer and 'startTimes' in immortalcontainer['status']:
            startTimes = immortalcontainer['status']['startTimes']+1
        else:
            startTimes = 1
        new_status['status'] = dict(
            currentPod=pod.metadata.name,
            startTimes=startTimes
        )
        return new_status

    def _new_pod(self, immortalcontainer):
        """Returns the pod definition to create the pod for an ImmortalContainer"""
        labels = dict(controller=immortalcontainer['metadata']['name'])
        return models.V1Pod(
            metadata=models.V1ObjectMeta(
                name=immortalcontainer['metadata']['name']+"-immortalpod",
                labels=labels,
                namespace=immortalcontainer['metadata']['namespace'],
                owner_references=[models.V1OwnerReference(
                    api_version=self.custom_group+"/"+self.custom_version,
                    controller=True,
                    kind=self.custom_kind,
                    name=immortalcontainer['metadata']['name'],
                    uid=immortalcontainer['metadata']['uid']
                )]),
            spec=models.V1PodSpec(
                containers=[
                    models.V1Container(
                        name="acontainer",
                        image=immortalcontainer['spec']['image']
                    )
                ]
            )
        )
