import logging
import threading

from kubernetes import watch

logger = logging.getLogger('threadedwatch')


class ThreadedWatcher(threading.Thread):
    """Watches Kubernetes resources event in a separate thread. Handlers for
    events can be registered using `add_handler`.

    Example:
        v1 = kubernetes.client.CoreV1Api()
        watcher = ThreadedWatcher(v1.list_pod_for_all_namespaces)
        def on_event(event):
            print(event)
        watcher.add_handler(on_event)
        watcher.start()
        watcher.join()
    """

    def __init__(self, func, *args, **kwargs):
        """Initialize this watcher.

        :param func: The API function pointer to watch. Any parameter to the 
                     function can be passed after this parameter.
        """
        super().__init__(daemon=True)
        self.func = func
        self.func_args = args
        self.func_kwargs = kwargs
        self.handlers = []
        self.watcher = None

    def add_handler(self, handler):
        """Adds a handler for all events seen by this watcher."""
        self.handlers.append(handler)

    def run(self):
        """Listen and dispatch events, this method should not be called
           directly, but using `start()`.
        """
        self.watcher = watch.Watch()
        stream = self.watcher.stream(
            self.func, *self.func_args, **self.func_kwargs)
        for event in stream:
            for handler in self.handlers:
                try:
                    handler(event)
                except:
                    logger.error("Error in event handler", exc_info=True)

    def stop(self):
        """Stops listening and dispatching events."""
        if self.watcher is not None:
            self.watcher.stop()
