from giblets import ComponentManager
from .signals import daemonized

component_manager = ComponentManager()

def on_daemonized(emitter):
    import logging
    log = logging.getLogger(__name__)
    for component_name, component in component_manager.components.iteritems():
        log.debug("Activating component: \"%s\"", component_name)
        component.activate()
        log.debug("Connecting signals for component: \"%s\"", component_name)
        component.connect_signals()

daemonized.connect(on_daemonized)
