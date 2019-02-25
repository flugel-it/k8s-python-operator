import logging
import sys

from kubernetes import client, config

import defs
from controller import Controller
from threadedwatch import ThreadedWatchStream

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

config.load_kube_config()

def main():
    corev1api = client.CoreV1Api()
    customsapi = client.CustomObjectsApi()

    # Changing this it's possible to work on all the namespaces or choose only one
    pods_watcher = ThreadedWatchStream(corev1api.list_pod_for_all_namespaces)
    immortalcontainers_watcher = ThreadedWatchStream(
        customsapi.list_cluster_custom_object, defs.CUSTOM_GROUP,
        defs.CUSTOM_VERSION, defs.CUSTOM_PLURAL
        )
    controller = Controller(pods_watcher, immortalcontainers_watcher, corev1api, 
                            customsapi, defs.CUSTOM_GROUP, defs.CUSTOM_VERSION,
                            defs.CUSTOM_PLURAL, defs.CUSTOM_KIND)

    controller.start()
    pods_watcher.start()
    immortalcontainers_watcher.start()
    try:
        controller.join()
    except (KeyboardInterrupt, SystemExit):
        print('\n! Received keyboard interrupt, quitting threads.\n')
        controller.stop()
        controller.join()

if __name__ == '__main__':
    main()