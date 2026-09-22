import threading

_thread_locals = threading.local()


def set_current_tenant(tenant):
    """Sets the active tenant for the current request thread."""
    setattr(_thread_locals, "tenant", tenant)


def get_current_tenant():
    """Gets the active tenant for the current request thread."""
    return getattr(_thread_locals, "tenant", None)


def clear_current_tenant():
    """Clears the active tenant from the current request thread."""
    if hasattr(_thread_locals, "tenant"):
        delattr(_thread_locals, "tenant")
