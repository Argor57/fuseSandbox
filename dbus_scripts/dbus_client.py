import dbus

def request_permission(resource):
    session_bus = dbus.SessionBus()
    permission_service = session_bus.get_object('org.example.PermissionService', '/org/example/PermissionService')
    permission_interface = dbus.Interface(permission_service, 'org.example.PermissionService')

    try:
        result = permission_interface.RequestPermission(resource)
        return result
    except dbus.DBusException as e:
        print(f"DBus Exception: {e}")
        return False
