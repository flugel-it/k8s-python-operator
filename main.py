import asyncio
import logging

from kubernetes import client, config, watch
import threading
import queue
import sys

logger = logging.getLogger('operator')
logger.setLevel(logging.INFO)

config.load_kube_config()


CUSTOM_GROUP = 'exampleoperator.flugel.it'
CUSTOM_VERSION = 'v1alpha1'
CUSTOM_PLURAL = 'immortalcontainers'


class ThreadedWatchStream(threading.Thread):
    def __init__(self, func, *args, **kwargs):
        super().__init__(daemon=True)
        self.func = func
        self.func_args = args
        self.func_kwargs = kwargs
        self.handlers = []
        self.watcher = None

    def add_handler(self, handler):
        self.handlers.append(handler)

    def run(self):
        self.watcher = watch.Watch()
        stream = self.watcher.stream(self.func, *self.func_args, **self.func_kwargs)
        for event in stream:
            for handler in self.handlers:
                handler(event)

    def stop(self):
        if self.watcher is not None:
            self.watcher.stop()


class Controller(threading.Thread):
    def __init__(self, pods_watcher, immortalcontainers_watcher):
        super().__init__()
        self.workqueue = queue.Queue(20)
        self.pods_watcher = pods_watcher
        self.immortalcontainers_watcher = immortalcontainers_watcher
        self.pods_watcher.add_handler(self.handle_pod_event)
        self.immortalcontainers_watcher.add_handler(self.handle_immortalcontainer_event)

    def handle_pod_event(self, event):
        self.workqueue.put(event['object'].metadata.name)

    def handle_immortalcontainer_event(self, event):
        self.workqueue.put(event['object']['metadata']['name'])

    def run(self):
        self.running = True
        while self.running:
            e = self.workqueue.get()
            if not self.running:
                self.workqueue.task_done()
                break
            try:
                self.sync(e)
                self.workqueue.task_done()
            except:
                logger.error("Error syncing {:s}".format(e))

    def stop(self):
        self.running = False
        self.workqueue.put(None)

    def sync(self, resource_key):
        logger.info("Syncing: {:s}".format(resource_key))


v1 = client.CoreV1Api()
customs = client.CustomObjectsApi()
pods_watcher = ThreadedWatchStream(v1.list_pod_for_all_namespaces)
immortalcontainers_watcher = ThreadedWatchStream(customs.list_cluster_custom_object, CUSTOM_GROUP, CUSTOM_VERSION, CUSTOM_PLURAL)
controller = Controller(pods_watcher, immortalcontainers_watcher)

controller.start()
pods_watcher.start()
immortalcontainers_watcher.start()

try:
    controller.join()
except (KeyboardInterrupt, SystemExit):
    print('\n! Received keyboard interrupt, quitting threads.\n')
    controller.stop()
    controller.join()

